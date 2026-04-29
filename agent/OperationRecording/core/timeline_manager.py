# -*- coding: utf-8 -*-
"""
动作时间线管理器，具有以下功能：
1. 时间序列动作执行
2. 并行动作叠加（overlays）
3. 动作优先级系统
4. 类人化效果应用
5. 支持暂停、恢复、停止
"""

import time
import random
from typing import List, Dict, Any, Optional, Callable, Union
from enum import Enum
from utils.logger import logger
from ..actions import action_registry


class ActionPriority(Enum):
    """
    动作优先级枚举

    取值：
    - LOW = 1
    - NORMAL = 2
    - HIGH = 3
    - CRITICAL = 4
    """
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class ActionState(Enum):
    """
    动作状态枚举

    取值：
    - SCHEDULED = 1（已计划）
    - RUNNING = 2（运行中）
    - PAUSED = 3（已暂停）
    - COMPLETED = 4（已完成）
    - CANCELLED = 5（已取消）
    """
    SCHEDULED = 1
    RUNNING = 2
    PAUSED = 3
    COMPLETED = 4
    CANCELLED = 5


class TimedAction:
    """
    带时间信息的动作

    参数说明：
    - action_name: 动作名称
    - params: 动作参数
    - start_time: 开始时间（相对于时间线）
    - duration: 持续时间（0 表示瞬时动作）
    - priority: 优先级，默认 NORMAL
    - blocking: 是否阻塞，默认 False
    - on_start: 开始回调，可选
    - on_end: 结束回调，可选
    """

    def __init__(self,
                 action_name: str,
                 params: Optional[Dict[str, Any]] = None,
                 start_time: float = 0.0,
                 duration: float = 0.0,
                 priority: ActionPriority = ActionPriority.NORMAL,
                 blocking: bool = False,
                 on_start: Optional[Callable[[], None]] = None,
                 on_end: Optional[Callable[[], None]] = None):
        self.action_name = action_name
        self.params: Dict[str, Any] = params if params is not None else {}
        self.start_time = start_time
        self.duration = duration
        self.priority = priority
        self.blocking = blocking
        self.on_start = on_start
        self.on_end = on_end
        self.state = ActionState.SCHEDULED
        self._start_timestamp = 0.0

    def is_instant(self) -> bool:
        """
        判断是否为瞬时动作

        返回：
        - bool: duration <= 0 时返回 True
        """
        return self.duration <= 0

    def should_start(self, timeline_time: float) -> bool:
        """
        判断是否应该开始执行

        参数：
        - timeline_time: 当前时间线时间

        返回：
        - bool: 是否可以开始
        """
        return self.state == ActionState.SCHEDULED and timeline_time >= self.start_time

    def should_end(self, timeline_time: float) -> bool:
        """
        判断是否应该结束

        参数：
        - timeline_time: 当前时间线时间

        返回：
        - bool: 是否可以结束
        """
        if self.is_instant():
            return False
        return self.state == ActionState.RUNNING and timeline_time >= self.start_time + self.duration

    def has_ended(self, timeline_time: float) -> bool:
        """
        判断是否已经结束

        参数：
        - timeline_time: 当前时间线时间

        返回：
        - bool: 是否已经结束
        """
        if self.is_instant():
            return self.state == ActionState.COMPLETED
        return timeline_time >= self.start_time + self.duration


class ActionTimeline:
    """
    动作时间线管理器

    功能说明：
    1. 时间线管理
       - from_sequence: 从序列创建时间线
       - start/pause/resume/stop: 控制时间线

    2. 动作执行
       - update: 更新时间线状态
       - _start_action/_stop_action/_execute_action: 执行动作

    3. 状态查询
       - get_status: 获取时间线状态
       - is_instant: 判断瞬时动作
    """

    def __init__(self, platform, context=None):
        """
        初始化时间线

        参数：
        - platform: 平台对象
        - context: MAA Context 对象，可选
        """
        self._platform = platform
        self._context = context
        self._actions: List[TimedAction] = []
        self._active_actions: Dict[str, TimedAction] = {}
        self._start_time = 0.0
        self._is_running = False
        self._paused = False
        self._speed = 1.0
        self._test_mode = False
        self._simulated_time = 0.0

        self._human_enabled = True
        self._min_delay_ms = 30
        self._max_delay_ms = 150
        self._acceleration_factor = 0.1

    def add_action(self, action: TimedAction):
        """
        添加动作到时间线

        参数：
        - action: 带时间信息的动作
        """
        self._actions.append(action)
        self._actions.sort(key=lambda x: x.start_time)

    def add_actions(self, actions: List[TimedAction]):
        """
        批量添加动作

        参数：
        - actions: 动作列表
        """
        for action in actions:
            self.add_action(action)

    def from_sequence(self, sequence: List[Dict[str, Any]]):
        """
        从序列数据创建时间线

        参数：
        - sequence: 序列数据列表

        执行流程：
        1. 遍历序列项
        2. 处理 wait 动作（仅增加时间）
        3. 添加主动作
        4. 添加叠加动作（overlays）
        5. 累加持续时间
        """
        current_time = 0.0

        for item in sequence:
            action_name: Optional[str] = item.get("action")
            if action_name is None:
                continue

            params: Dict[str, Any] = item.get("params", {}) or {}

            if action_name == "wait":
                # 优先使用 until 参数（等待到目标时间点）
                until = params.get("until")
                if isinstance(until, (int, float)):
                    # 计算需要等待的时间
                    wait_time = max(0.0, until - current_time)
                    current_time += wait_time
                else:
                    # 使用 duration 参数（等待指定时长）
                    duration = params.get("duration", item.get("duration", 1.0))
                    if isinstance(duration, (int, float)):
                        current_time += duration
                continue

            duration: float = float(params.get("duration", item.get("duration", 0.0)))
            overlays: List[Dict[str, Any]] = params.get("overlays", item.get("overlays", [])) or []

            self.add_action(TimedAction(
                action_name=action_name,
                params=params,
                start_time=current_time,
                duration=duration,
                priority=ActionPriority.NORMAL
            ))

            for overlay in overlays:
                overlay_action: Optional[str] = overlay.get("action")
                if overlay_action is None:
                    continue

                overlay_params: Dict[str, Any] = overlay.get("params", {}) or {}
                overlay_at: float = float(overlay.get("at", 0.0))

                self.add_action(TimedAction(
                    action_name=overlay_action,
                    params=overlay_params,
                    start_time=current_time + overlay_at,
                    duration=0,
                    priority=ActionPriority.HIGH,
                    blocking=False
                ))

            current_time += duration

    def start(self):
        """
        启动时间线

        执行流程：
        1. 记录开始时间
        2. 标记运行中
        3. 重置暂停状态
        4. 重置所有动作状态为已计划
        """
        self._start_time = time.time()
        self._is_running = True
        self._paused = False
        self._simulated_time = 0.0

        for action in self._actions:
            action.state = ActionState.SCHEDULED

    def pause(self):
        """暂停时间线"""
        self._paused = True

    def resume(self):
        """
        恢复时间线

        执行流程：
        1. 重置暂停状态
        2. 调整开始时间以保持已流逝时间
        """
        self._paused = False
        self._start_time = time.time() - self._get_elapsed_time()

    def stop(self):
        """
        停止时间线

        执行流程：
        1. 标记非运行
        2. 停止所有活跃动作
        """
        self._is_running = False
        for action_name, action in self._active_actions.items():
            self._stop_action(action)

    def update(self):
        """
        更新时间线状态

        执行流程：
        1. 检查是否运行或暂停
        2. 获取已流逝时间
        3. 检查并启动准备好的动作
        4. 检查并停止应结束的动作
        5. 检查是否完全完成
        """
        if not self._is_running or self._paused:
            return

        elapsed = self._get_elapsed_time()

        if self._test_mode:
            self._simulated_time += 0.5

        for action in self._actions:
            if action.should_start(elapsed):
                self._start_action(action)

        completed_actions: List[str] = []
        for action_name, action in self._active_actions.items():
            if action.should_end(elapsed):
                completed_actions.append(action_name)

        for action_name in completed_actions:
            action = self._active_actions.pop(action_name)
            self._stop_action(action)

        if self._is_complete(elapsed):
            self.stop()

    def set_test_mode(self, enabled: bool):
        """
        设置测试模式

        参数：
        - enabled: 是否启用测试模式
        """
        self._test_mode = enabled

    def _get_elapsed_time(self) -> float:
        """
        获取已流逝的时间

        返回：
        - float: 已流逝时间（秒）

        执行流程：
        1. 测试模式：返回模拟时间
        2. 正常模式：计算真实流逝时间 * 速度
        """
        if self._test_mode:
            return self._simulated_time
        return (time.time() - self._start_time) * self._speed

    def _start_action(self, action: TimedAction):
        """
        开始执行动作

        参数：
        - action: 要执行的动作

        执行流程：
        1. 检查类人化（非瞬时），添加延迟
        2. 检查是否有阻塞性动作冲突
        3. 更新状态为运行中
        4. 执行动作
        5. 瞬时动作立即完成
        6. 调用开始回调
        """
        if self._human_enabled and not action.is_instant():
            self._human_delay()

        try:
            can_execute = True
            for active_action in self._active_actions.values():
                if active_action.blocking and action.priority.value <= active_action.priority.value:
                    can_execute = False
                    break

            if can_execute:
                action.state = ActionState.RUNNING
                action._start_timestamp = time.time()

                self._execute_action(action, is_start=True)

                if action.is_instant():
                    action.state = ActionState.COMPLETED
                    if action.on_end:
                        action.on_end()
                else:
                    self._active_actions[action.action_name] = action

                if action.on_start:
                    action.on_start()
        except Exception:
            pass

    def _stop_action(self, action: TimedAction):
        """
        停止执行动作

        参数：
        - action: 要停止的动作

        执行流程：
        1. 特定动作特殊处理（move/charge_attack 释放摇杆）
        2. 标记状态为已完成
        3. 调用结束回调
        """
        if action.action_name == "move":
            if hasattr(self._platform, "release_joystick"):
                self._platform.release_joystick()
        elif action.action_name == "charge_attack":
            if hasattr(self._platform, "release_charge_attack"):
                self._platform.release_charge_attack()

        action.state = ActionState.COMPLETED

        if action.on_end:
            action.on_end()

    def _execute_action(self, action: TimedAction, is_start: bool = True):
        """
        执行动作

        参数：
        - action: 要执行的动作
        - is_start: 是否为开始阶段（结束阶段为 False）

        执行流程：
        1. 应用类人化效果
        2. 优先使用平台方法（move、charge_attack 等）
        3. 如果没有平台方法（比如 run_node），使用 action_registry 执行
        """
        params = self._apply_human_effects(action)

        try:
            method = getattr(self._platform, action.action_name, None)
            
            if method is not None:
                # 有平台方法，使用原来的方式，保证流畅和时间准确
                duration_factor = 0 if self._test_mode else 1

                if action.action_name == "move":
                    direction = params.get("direction", "center")
                    duration = 0 if is_start else (action.duration if action.duration > 0 else 0.1) * duration_factor
                    method(direction, duration)
                elif action.action_name == "charge_attack":
                    duration = 0 if is_start else (action.duration if action.duration > 0 else 0.5) * duration_factor
                    x = params.get("x")
                    y = params.get("y")
                    method(duration, x, y)
                elif action.action_name == "dodge":
                    direction = params.get("direction")
                    if direction:
                        method(direction)
                    else:
                        method()
                elif action.action_name == "turn":
                    angle = params.get("angle", 0.0)
                    method(angle)
                elif action.action_name == "interact":
                    interaction_type = params.get("interaction_type", "default")
                    method(interaction_type)
                elif action.action_name == "swipe":
                    start_x = params.get("start_x", 0)
                    start_y = params.get("start_y", 0)
                    end_x = params.get("end_x", 0)
                    end_y = params.get("end_y", 0)
                    duration = (action.duration if action.duration > 0 else 0.5) * duration_factor
                    method(start_x, start_y, end_x, end_y, duration)
                elif action.action_name == "click":
                    x = params.get("x", 0)
                    y = params.get("y", 0)
                    method(x, y)
                elif action.action_name == "press_key":
                    key = params.get("key", "")
                    duration = (action.duration if action.duration > 0 else 0.1) * duration_factor
                    method(key, duration)
                else:
                    method()
            else:
                # 没有平台方法，尝试用 action_registry 执行（比如 run_node）
                # 对于瞬时动作，只在 is_start=True 时执行一次
                if action.is_instant() and not is_start:
                    return
                
                action_obj = action_registry.create_action(action.action_name, self._platform, self._context)
                
                if action_obj:
                    result = action_obj.execute(params)

        except Exception as e:
            logger.error(f"[TimelineManager] _execute_action 异常: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"[TimelineManager] 堆栈信息:\n{traceback.format_exc()}")

    def _apply_human_effects(self, action: TimedAction) -> Dict[str, Any]:
        """
        应用类人化效果

        参数：
        - action: 动作对象

        返回：
        - Dict[str, Any]: 处理后的参数

        执行流程：
        1. 复制参数
        2. move 动作添加加速标记
        3. jump 动作添加随机延迟
        """
        params = action.params.copy()

        if not self._human_enabled:
            return params

        if action.action_name == "move" and action.duration > 0:
            params['acceleration'] = True
            params['deceleration'] = True

        if action.action_name == "jump":
            params['random_delay'] = random.uniform(0.02, 0.08)

        return params

    def _human_delay(self):
        """
        添加类人化随机延迟

        执行流程：
        1. 计算随机延迟
        2. sleep 延迟时间
        """
        delay = random.uniform(self._min_delay_ms, self._max_delay_ms) / 1000.0
        time.sleep(delay)

    def _is_complete(self, elapsed: float) -> bool:
        """
        判断时间线是否已完成

        参数：
        - elapsed: 已流逝时间

        返回：
        - bool: 是否已完成

        执行流程：
        1. 无动作：已完成
        2. 任何动作未结束：未完成
        3. 无活跃动作且超过最后一个动作结束时间：已完成
        """
        if not self._actions:
            return True

        for action in self._actions:
            if not action.has_ended(elapsed):
                return False

        if not self._active_actions:
            last_action = self._actions[-1]
            if self._test_mode or elapsed >= last_action.start_time + max(last_action.duration, 0.001):
                return True

        return False

    def get_status(self) -> Dict[str, Any]:
        """
        获取时间线状态

        返回：
        - Dict[str, Any]: 状态字典
          - is_running: 是否运行中
          - is_paused: 是否暂停
          - elapsed_time: 已流逝时间
          - active_actions: 活跃动作列表
          - total_actions: 总动作数
        """
        return {
            "is_running": self._is_running,
            "is_paused": self._paused,
            "elapsed_time": self._get_elapsed_time(),
            "active_actions": list(self._active_actions.keys()),
            "total_actions": len(self._actions)
        }
