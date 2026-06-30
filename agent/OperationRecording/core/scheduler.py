# -*- coding: utf-8 -*-
"""
事件队列调度器

将 ActionNode 树展平为事件列表，按时间顺序消费事件。
替代原有的轮询式 ActionTimeline，实现了：
1. 事件优先队列（O(log n) 取下一事件，零遍历）
2. smooth_transition 通用协议（不再硬编码 "move"）
3. 事件排序保证 END 先于 START（同时间点先释放旧动作再启动新动作）
"""

import time
import traceback
from typing import Any, Dict, List

from .event import ActionEvent
from .node import ActionNode
from ..actions import action_registry
from ..effects import EffectManager
from utils.logger import logger


class EventScheduler:
    """
    事件队列调度器

    功能说明：
    1. 加载节点树
       - load: 将 ActionNode.flatten() 生成的事件排序入库
    2. 执行循环
       - run: 按时间顺序消费事件，支持停止检测
    3. 事件处理
       - _handle_start: 持续动作的按下阶段
       - _handle_end:   持续动作的释放阶段（含 smooth_transition 检测）
       - _handle_execute: 瞬时动作执行
    4. 控制
       - stop: 释放所有活跃动作
    """

    # 同时间点事件排序：END (0) < START (1) < EXECUTE (2)
    # 保证「先结束旧动作，再启动新动作」
    _PHASE_ORDER: Dict[str, int] = {"end": 0, "start": 1, "execute": 2}

    def __init__(self, platform, context=None, effect_manager=None):
        """
        初始化调度器

        参数：
        - platform: 平台实例
        - context: MAA Context 对象，可选
        - effect_manager: 效果管理器，可选
        """
        self._platform = platform
        self._context = context
        self._effect_manager = effect_manager or EffectManager()
        self._events: List[ActionEvent] = []
        self._active: Dict[int, ActionEvent] = {}  # action_id → 对应的 start 事件
        self._id_counter = 0
        self._start_time = 0.0
        self._is_running = False

    def _next_id(self) -> int:
        """生成唯一的 action_id，用于配对 start/end 事件"""
        self._id_counter += 1
        return self._id_counter

    def load(self, node: ActionNode) -> None:
        """
        加载动作节点树

        参数：
        - node: 动作节点树根节点

        执行流程：
        1. 将节点树展平为事件列表
        2. 按 (time, phase_order) 排序
        """
        self._events = node.flatten(0.0, self._next_id)
        self._events.sort(key=lambda e: (e.time, self._PHASE_ORDER.get(e.phase, 3)))

    def run(self) -> bool:
        """
        运行事件循环

        返回：
        - bool: 是否正常完成（False 表示被停止信号中断）

        执行流程：
        1. 记录开始时间
        2. 循环处理事件，每次检查停止信号
        3. sleep 到下一事件时间（最多 50ms 防止 CPU 空转）
        """
        self._start_time = time.time()
        self._is_running = True

        while self._events and self._is_running:
            if self._context is not None and getattr(self._context.tasker, 'stopping', False):
                self._platform.release_all()
                return False

            now = time.time() - self._start_time
            next_event = self._events[0]

            if next_event.time > now:
                time.sleep(min(next_event.time - now, 0.05))
                continue

            self._events.pop(0)
            self._process(next_event)

        self._is_running = False
        return True

    def _process(self, event: ActionEvent) -> None:
        """根据事件阶段分发处理"""
        try:
            if event.phase == "start":
                self._handle_start(event)
            elif event.phase == "end":
                self._handle_end(event)
            elif event.phase == "execute":
                self._handle_execute(event)
        except Exception as e:
            logger.error(f"[EventScheduler] _process 异常: {type(e).__name__}: {e}")
            logger.error(f"[EventScheduler] 堆栈信息:\n{traceback.format_exc()}")

    def _handle_start(self, event: ActionEvent) -> None:
        """
        处理持续动作的按下阶段

        参数：
        - event: 开始事件

        执行流程：
        1. Effects pre_action 延迟
        2. 创建动作实例并调用 start()
        3. 记录到活跃列表

        注：节点树（Sequence/Parallel/AtOffset）已编码时序约束，
        展平后的事件列表即为执行真理，无需额外的运行时冲突检查。
        """
        event_context = {
            "duration": event.duration,
            "is_instant": False,
            "is_timeline": True,
        }

        if self._effect_manager is not None:
            pre_delay = self._effect_manager.pre_action(event.action_name, event_context)
            if pre_delay > 0:
                time.sleep(pre_delay)

        try:
            action_obj = action_registry.create_action(event.action_name, self._platform, self._context)
            if action_obj is not None:
                params = (
                    self._effect_manager.apply_effects(event.action_name, event.params, event_context)
                    if self._effect_manager is not None
                    else event.params
                )

                if not action_obj.start(params):
                    logger.warning(f"[EventScheduler] start({event.action_name!r}) 失败")
                    return

                self._active[event.action_id] = event
        except Exception as e:
            logger.error(f"[EventScheduler] _handle_start 异常: {type(e).__name__}: {e}")
            logger.error(f"[EventScheduler] 堆栈信息:\n{traceback.format_exc()}")

    def _handle_end(self, event: ActionEvent) -> None:
        """
        处理持续动作的释放阶段

        参数：
        - event: 结束事件

        执行流程：
        1. 检测 smooth_transition（同时间点有同类型 start 事件 → 平滑过渡）
        2. 否则正常释放（release_action）
        3. 从活跃列表移除
        4. Effects post_action
        """
        action_cls = action_registry.get(event.action_name)

        # 检测连续同类型动作的平滑过渡
        if action_cls and action_cls.timeline_meta.smooth_transition and self._events:
            next_event = self._events[0]
            if (
                next_event.phase == "start"
                and next_event.action_name == event.action_name
                and abs(next_event.time - event.time) < 0.001
            ):
                # 弹出下一个 start 事件（后续循环不重复处理）
                self._events.pop(0)
                old_direction = event.params.get("direction", "")
                new_direction = next_event.params.get("direction", "")
                self._platform.cleanup_direction(event.action_name, old_direction, new_direction)

                if event.action_id in self._active:
                    del self._active[event.action_id]
                return

        # 正常释放：通过 action.stop() 释放，支持子类自定义释放逻辑
        if action_cls and action_cls.timeline_meta.has_duration:
            try:
                action_obj = action_registry.create_action(event.action_name, self._platform, self._context)
                if action_obj is not None:
                    params = (
                        self._effect_manager.apply_effects(event.action_name, event.params, {})
                        if self._effect_manager is not None
                        else event.params
                    )
                    if not action_obj.stop(params):
                        logger.warning(f"[EventScheduler] stop({event.action_name!r}) 失败")
            except Exception as e:
                logger.error(f"[EventScheduler] stop({event.action_name!r}) 异常: {type(e).__name__}: {e}")

        if event.action_id in self._active:
            del self._active[event.action_id]

        if self._effect_manager is not None:
            post_context = {
                "duration": event.duration,
                "is_instant": False,
                "is_timeline": True,
            }
            self._effect_manager.post_action(event.action_name, post_context)

    def _handle_execute(self, event: ActionEvent) -> None:
        """
        处理瞬时动作

        参数：
        - event: 执行事件

        执行流程：
        1. Effects pre_action 延迟
        2. 创建动作实例并调用 execute()
        3. Effects post_action

        注意：不检查 _can_execute，因为瞬时动作应能与并行的持续动作同时执行
        （如 move 过程中 dodge overlay）
        """
        event_context = {
            "duration": 0,
            "is_instant": True,
            "is_timeline": True,
        }

        if self._effect_manager is not None:
            pre_delay = self._effect_manager.pre_action(event.action_name, event_context)
            if pre_delay > 0:
                time.sleep(pre_delay)

        try:
            action_obj = action_registry.create_action(event.action_name, self._platform, self._context)
            if action_obj is not None:
                params = (
                    self._effect_manager.apply_effects(event.action_name, event.params, event_context)
                    if self._effect_manager is not None
                    else event.params
                )
                if not action_obj.execute(params):
                    logger.warning(f"[EventScheduler] execute({event.action_name!r}) 失败")
        except Exception as e:
            logger.error(f"[EventScheduler] _handle_execute 异常: {type(e).__name__}: {e}")
            logger.error(f"[EventScheduler] 堆栈信息:\n{traceback.format_exc()}")

        if self._effect_manager is not None:
            self._effect_manager.post_action(event.action_name, event_context)

    def stop(self) -> None:
        """
        停止调度器

        执行流程：
        1. 标记非运行
        2. 通过 action.stop() 释放所有活跃动作
        """
        self._is_running = False
        for action_id in list(self._active.keys()):
            event = self._active.pop(action_id)
            action_cls = action_registry.get(event.action_name)
            if action_cls and action_cls.timeline_meta.has_duration:
                try:
                    action_obj = action_registry.create_action(event.action_name, self._platform, self._context)
                    if action_obj is not None:
                        action_obj.stop(event.params)
                except Exception as e:
                    logger.error(f"[EventScheduler] stop({event.action_name!r}) 异常: {type(e).__name__}: {e}")

    @property
    def is_running(self) -> bool:
        """调度器是否正在运行"""
        return self._is_running
