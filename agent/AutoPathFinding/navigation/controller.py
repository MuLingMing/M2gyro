# -*- coding: utf-8 -*-
"""
导航控制器：会话生命周期 + 单帧编排（感知→估计→决策→执行）。

修复旧版缺陷：
- 按 node_name 显式管理会话（create/reset），替代无生命周期的 ClassVar 全局态
- phase 只在 policy 单处赋值
- 卡住超时/EMA 自适应转速/转向分级全部真实接线
"""

from __future__ import annotations

import time
from typing import Dict, Optional

import numpy as np
from maa.context import Context

from utils.logger import logger

from ..selector import TargetInfo, TargetSelector, create_selector
from .estimator import LockedTarget, MovementState, TargetEstimator
from .executor import NavExecutor
from .geometry import angle_diff
from .minimap import MinimapTracker
from .params import NavigationParams
from .perception import TURN_CLIP_HORIZONTAL, TURN_CLIP_VERTICAL, ScreenPerceiver
from .policy import Decision, NavPhase, decide


class NavigationSession:
    """单节点导航会话（一个 pipeline 节点一份实例）。"""

    def __init__(self, node_name: str, params: NavigationParams) -> None:
        self.node_name = node_name
        self.params = params
        self.estimator = TargetEstimator(params)
        self.movement = MovementState()
        self.selector: TargetSelector = create_selector(
            params.selector_type, params.selector_priority
        )
        self.locked: Optional[LockedTarget] = None
        self.last_direction: Optional[str] = None
        self.started_at_ms = int(time.monotonic() * 1000)
        self.last_decision_phase: Optional[NavPhase] = None
        self.last_detail: Optional[Dict] = None
        self._perceiver: Optional[ScreenPerceiver] = None
        self._executor: Optional[NavExecutor] = None
        # 小地图自状态（第一档；enable_minimap=False 时 update 直接返回无效观测）
        self.minimap = MinimapTracker(params)
        self._last_heading: Optional[float] = None

    def bind_context(self, context: Context) -> None:
        """绑定/更新 MaaFW Context（reco 与 action 回调各自传入）。"""
        if self._perceiver is None:
            self._perceiver = ScreenPerceiver(context)
        if self._executor is None:
            self._executor = NavExecutor(context)

    @property
    def elapsed_ms(self) -> int:
        """会话累计时长（ms）。"""
        return int(time.monotonic() * 1000) - self.started_at_ms

    def reset(self, params: Optional[NavigationParams] = None) -> None:
        """重置会话（可选更新参数）。"""
        if params is not None:
            self.params = params
            self.estimator = TargetEstimator(params)
            self.selector = create_selector(
                params.selector_type, params.selector_priority
            )
            self.minimap = MinimapTracker(params)
        self.movement = MovementState()
        self.locked = None
        self.last_direction = None
        self.started_at_ms = int(time.monotonic() * 1000)
        self.last_decision_phase = None
        self._last_heading = None

    # ===== 单帧：识别侧 =====

    def perceive(self, context: Context, image: np.ndarray) -> Dict:
        """识别回调：输出当帧 detail（含 phase，供 pipeline next 分支）。"""
        self.bind_context(context)
        params = self.params

        # 0. 小地图自状态（朝向/速度；未启用时为无效观测，策略走旧开环逻辑）
        minimap_obs = self.minimap.update(image)
        self.movement.heading = minimap_obs.heading_deg
        self.movement.heading_valid = minimap_obs.heading_valid
        self.movement.speed_px_s = minimap_obs.speed_px_s
        self.movement.speed_valid = minimap_obs.speed_valid
        if minimap_obs.heading_valid and minimap_obs.heading_deg is not None:
            if self._last_heading is not None:
                self.movement.cumulative_turn_deg += abs(
                    angle_diff(minimap_obs.heading_deg, self._last_heading)
                )
            self._last_heading = minimap_obs.heading_deg
        else:
            self._last_heading = None

        # 1. 感知（fast path ROI 收缩）
        roi = self.estimator.resolve_fast_path_roi(self.movement, self.locked)
        targets = self._perceiver.collect_targets(image, params, roi=roi)
        if not targets and roi is not None:
            # fast path 未命中：退回全 ROI 重试并累计 miss
            self.movement.fast_path_miss_count += 1
            targets = self._perceiver.collect_targets(image, params, roi=None)
        else:
            self.movement.fast_path_miss_count = 0

        # 2. 锁定/追踪 + 选择
        locked, switched = self.estimator.resolve_locked_target(
            self.locked, targets, self.selector
        )
        if switched:
            self.movement = MovementState()
            self.estimator.reset_target()
        self.locked = locked
        target = None
        if locked is not None:
            target = TargetInfo(
                template=locked.template,
                center=locked.center,
                bbox=locked.bbox,
                score=locked.score,
                distance=locked.distance,
            )

        # 3. 距离 OCR
        if target is not None:
            target = self._perceiver.extract_distance(image, target, params)
            if target.distance is None:
                self.movement.distance_miss_count += 1
            else:
                self.movement.distance_miss_count = 0
            # 重新发现目标：SEARCH 环视累计清零
            self.movement.cumulative_turn_deg = 0.0

        # 4. 帧状态估计
        self.movement.target = target
        self.movement.distance = target.distance if target else None
        self.movement.stuck_frames = self.estimator.stuck.consecutive_stuck
        self.estimator.estimate(self.movement, self.last_direction)
        self.last_direction = self.movement.direction

        # 5. 转向坐标（距离缺失或偏心时预计算，供 policy 使用）
        self._refresh_turn_coordinates()

        # 6. 卡住检测（目标中心/距离变化 + 小地图速度判据）
        center = target.center if target else None
        self.estimator.stuck.update(
            center,
            self.movement.distance,
            speed=minimap_obs.speed_px_s if minimap_obs.speed_valid else None,
        )

        # 7. 决策（纯函数）
        decision = decide(
            self.movement,
            params,
            stuck_duration_ms=self.estimator.stuck.stuck_duration_ms,
            elapsed_ms=self.elapsed_ms,
            locked=locked is not None,
        )
        self.last_decision_phase = decision.phase

        hit = decision.phase not in (NavPhase.FAIL,)
        detail = self._build_detail(decision, hit)
        self.last_detail = detail
        return detail

    # ===== 单帧：动作侧 =====

    def act(self, context: Context, detail: Dict) -> bool:
        """动作回调：执行识别侧决策出的命令序列。"""
        self.bind_context(context)
        commands = detail.get("commands", [])
        from .geometry import TurnGrade
        from .policy import Command, CommandType

        for raw in commands:
            tasker = getattr(context, "tasker", None)
            if tasker is not None and getattr(tasker, "stopping", False):
                return False
            grade_raw = raw.get("turn_grade", "fine_tune")
            grade = TurnGrade(grade_raw) if isinstance(grade_raw, str) else grade_raw
            command = Command(
                type=CommandType(raw.get("type", "none")),
                direction=raw.get("direction"),
                duration_s=raw.get("duration_s"),
                turn_coordinates=(
                    tuple(tuple(p) for p in raw["turn_coordinates"])
                    if raw.get("turn_coordinates")
                    else None
                ),
                turn_grade=grade,
                release_before=raw.get("release_before", False),
            )
            if not self._executor._execute_one(command, self.params):
                return False
        if detail.get("phase") in ("arrive", "fail"):
            self._executor.release_all()
        return True

    # ===== 内部 =====

    def _refresh_turn_coordinates(self) -> None:
        """距离缺失或偏心超死区时计算转向坐标（含 EMA 自适应转速）。"""
        params = self.params
        target = self.movement.target
        need_turn = self.movement.distance is None or not self.movement.in_dead_zone
        if target is None or not params.enable_turning or not need_turn:
            self.movement.turn_coordinates = None
            return

        from .geometry import compute_turn_coordinates

        speed = self.estimator.adaptive_speed(self.movement.deviation)
        coords = compute_turn_coordinates(
            target.center,
            self.movement.turn_attempt,
            min_turn_distance=params.min_turn_distance,
            max_turn_distance=params.max_turn_distance,
            distance_missing_turn_scale=params.distance_missing_turn_scale,
            turn_min_floor_ratio=params.turn_min_floor_ratio,
            horizontal_clip=TURN_CLIP_HORIZONTAL,
            vertical_clip=TURN_CLIP_VERTICAL,
            adaptive_speed=speed,
            screen_center=(640, 360),
            speed_factor=params.turn_speed_factor,
        )
        previous = self.movement.turn_coordinates
        self.movement.turn_coordinates = coords
        if coords is not None and previous is not None and coords != previous:
            self.movement.turn_attempt += 1
        elif coords is None:
            self.movement.turn_attempt = 0
        if self.movement.turn_attempt > params.max_turn_attempts:
            self.movement.turn_attempt = params.max_turn_attempts

    def _build_detail(self, decision: Decision, hit: bool) -> Dict:
        """构造 pipeline detail（含命令序列，action 侧按序执行）。"""
        commands = []
        for c in decision.commands:
            commands.append(
                {
                    "type": c.type.value,
                    "direction": c.direction,
                    "duration_s": c.duration_s,
                    "turn_coordinates": (
                        [list(p) for p in c.turn_coordinates]
                        if c.turn_coordinates
                        else None
                    ),
                    "turn_grade": (
                        c.turn_grade.value if hasattr(c.turn_grade, "value") else c.turn_grade
                    ),
                    "release_before": c.release_before,
                }
            )
        return {
            "phase": decision.phase.value,
            "hit": hit,
            "commands": commands,
            "distance": self.movement.distance,
            "direction": self.movement.direction,
            "deviation": round(self.movement.deviation, 1),
            "in_dead_zone": self.movement.in_dead_zone,
            "turn_attempt": self.movement.turn_attempt,
            "locked": self.locked is not None,
            "heading": round(self.movement.heading, 1) if self.movement.heading else None,
            "speed_px_s": (
                round(self.movement.speed_px_s, 1) if self.movement.speed_px_s is not None else None
            ),
            "cumulative_turn_deg": round(self.movement.cumulative_turn_deg, 1),
            "stuck_duration_ms": self.estimator.stuck.stuck_duration_ms,
            "elapsed_ms": self.elapsed_ms,
            "detail": decision.detail,
        }


class NavigationController:
    """会话注册表：按 node_name 索引，显式 create/reset 生命周期。"""

    def __init__(self) -> None:
        self._sessions: Dict[str, NavigationSession] = {}

    def get(self, node_name: str) -> Optional[NavigationSession]:
        """获取会话（不存在返回 None）。"""
        return self._sessions.get(node_name)

    def get_or_create(
        self,
        node_name: str,
        params: Optional[NavigationParams] = None,
    ) -> NavigationSession:
        """获取或创建会话。"""
        session = self._sessions.get(node_name)
        if session is None:
            session = NavigationSession(
                node_name,
                params or NavigationParams.from_dict(None),
            )
            self._sessions[node_name] = session
        return session

    def create(
        self,
        node_name: str,
        params: Optional[NavigationParams] = None,
    ) -> NavigationSession:
        """（重）创建会话，覆盖同名的旧会话。"""
        session = NavigationSession(
            node_name, params or NavigationParams.from_dict(None)
        )
        self._sessions[node_name] = session
        return session

    def reset(self, node_name: str) -> bool:
        """重置指定会话。"""
        session = self._sessions.get(node_name)
        if session is None:
            return False
        session.reset()
        return True

    def release(self, node_name: str) -> bool:
        """释放指定会话（松键 + 移除）。"""
        session = self._sessions.pop(node_name, None)
        if session is None:
            return False
        if session._executor is not None:
            session._executor.release_all()
            session._executor.reset_platform()
        return True

    def release_all_sessions(self) -> int:
        """释放全部会话（进程停止兜底）。"""
        count = 0
        for name in list(self._sessions):
            if self.release(name):
                count += 1
        return count


# 模块级唯一实例（custom 回调入口共享；生命周期经 Init/Release action 显式管理）
controller = NavigationController()
