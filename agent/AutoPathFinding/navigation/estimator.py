# -*- coding: utf-8 -*-
"""
估计层：目标锁定/追踪、方位估计、卡住检测、转向自适应。

从旧 state/path_finding_state.py 与 reco 的锁定逻辑移植并修复：
- stuck_timeout_ms 真实生效（旧版 StuckDetector.entered_at_ms 只记录不判断）
- RotationAdjuster EMA 输出接入 compute_turn_distance 的 adaptive_speed
  （旧版 update() 仅测试调用，生产恒 speed=1.0）
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from ..selector import TargetInfo
from .geometry import (
    SCREEN_CENTER,
    TurnGrade,
    angle_diff,
    classify_turn,
    compute_target_angle,
    deviation_angle,
)
from .params import NavigationParams


@dataclass
class LockedTarget:
    """已锁定的目标（含锁定 id 与追踪计数）。"""

    lock_id: str
    template: str
    bbox: Tuple[float, float, float, float]
    center: Tuple[float, float]
    score: float
    distance: Optional[int] = None
    miss_count: int = 0

    @staticmethod
    def generate_lock_id(template: str) -> str:
        """生成唯一锁定 id（模板名 + 时间戳 + 随机后缀）。"""
        import random

        return f"{template}_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"

    def iou(self, bbox: Tuple[float, float, float, float]) -> float:
        """计算给定 bbox 与锁定 bbox 的交并比。"""
        ax, ay, aw, ah = self.bbox
        bx, by, bw, bh = bbox
        ix = max(ax, bx)
        iy = max(ay, by)
        ix2 = min(ax + aw, bx + bw)
        iy2 = min(ay + ah, by + bh)
        iw = max(0.0, ix2 - ix)
        ih = max(0.0, iy2 - iy)
        inter = iw * ih
        union = aw * ah + bw * bh - inter
        return inter / union if union > 0 else 0.0


@dataclass
class MovementState:
    """单次会话内的运动状态（每帧由估计器更新）。"""

    locked_target: Optional[LockedTarget] = None
    target: Optional[TargetInfo] = None
    distance: Optional[int] = None
    direction: Optional[str] = None
    offset: Tuple[float, float] = (0.0, 0.0)
    offset_norm: float = 0.0
    deviation: float = 0.0
    turn_grade: TurnGrade = TurnGrade.FINE_TUNE
    fast_path_roi: Optional[Tuple[int, int, int, int]] = None
    fast_path_miss_count: int = 0
    distance_miss_count: int = 0
    turn_attempt: int = 0
    in_dead_zone: bool = False
    lock_miss_count: int = 0
    stuck_frames: int = 0
    turn_coordinates: Optional[Tuple[Tuple[int, int], Tuple[int, int]]] = None
    # ===== 小地图自状态（第一档；heading_valid=False 时策略走旧开环逻辑） =====
    heading: Optional[float] = None
    heading_valid: bool = False
    speed_px_s: Optional[float] = None
    speed_valid: bool = False
    target_angle: Optional[float] = None
    # SEARCH 环视累计转角（度；有目标时清零）
    cumulative_turn_deg: float = 0.0


class RotationAdjuster:
    """EMA 平滑的自适应转速（修复：输出真实接入转向距离计算）。

    偏差角越大转速系数越高，经 EMA 平滑避免抖动：
    alpha_up=0.618（升速快）、alpha_down=0.382（降速缓）。
    """

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._speed = 1.0

    def update(self, deviation_deg: float, lower: float, upper: float) -> float:
        """按当前偏差角更新并返回自适应转速系数（0.5~1.5）。"""
        if not self.enabled:
            return 1.0
        if deviation_deg >= upper:
            target = 1.5
        elif deviation_deg <= lower:
            target = 0.5
        else:
            ratio = (deviation_deg - lower) / max(upper - lower, 1e-6)
            target = 0.5 + ratio
        alpha = 0.618 if target > self._speed else 0.382
        self._speed = alpha * target + (1 - alpha) * self._speed
        return self._speed

    def reset(self) -> None:
        """重置平滑值。"""
        self._speed = 1.0


class StuckDetector:
    """卡住检测（修复：stuck_timeout_ms 真实生效）。"""

    def __init__(self, params: NavigationParams) -> None:
        self._params = params
        self._consecutive_stuck = 0
        self._entered_at_ms: Optional[int] = None
        self._last_center: Optional[Tuple[float, float]] = None
        self._last_distance: Optional[int] = None

    @property
    def consecutive_stuck(self) -> int:
        """连续卡住帧数。"""
        return self._consecutive_stuck

    @property
    def stuck_duration_ms(self) -> int:
        """已持续卡住的时长（ms，未卡住为 0）。"""
        if self._entered_at_ms is None:
            return 0
        return int(time.monotonic() * 1000) - self._entered_at_ms

    @property
    def is_stuck(self) -> bool:
        """连续卡住帧数达到阈值即视为卡住。"""
        return self._consecutive_stuck >= self._params.stuck_threshold

    @property
    def is_timeout(self) -> bool:
        """卡住持续时长超过 stuck_timeout_ms（修复：旧版该参数不生效）。"""
        return self.is_stuck and self.stuck_duration_ms > self._params.stuck_timeout_ms

    def update(
        self,
        center: Optional[Tuple[float, float]],
        distance: Optional[int],
        speed: Optional[float] = None,
    ) -> None:
        """按帧更新卡住判定。

        判据（优先级从高到低）:
        - 小地图速度有效时以其为准：speed > speed_stuck_px_s 视为在动（覆盖其余判据），
          否则视为原地
        - 中心位移与距离变化均小于容差计一帧卡住
        - 中心与距离均缺失计一帧卡住
        """
        stuck_frame = False
        if center is not None and self._last_center is not None:
            dx = abs(center[0] - self._last_center[0])
            dy = abs(center[1] - self._last_center[1])
            if (
                dx <= self._params.stuck_center_tolerance
                and dy <= self._params.stuck_center_tolerance
            ):
                stuck_frame = True
        if (
            distance is not None
            and self._last_distance is not None
            and abs(distance - self._last_distance)
            <= self._params.stuck_distance_tolerance
        ):
            stuck_frame = True
        if center is None and distance is None:
            stuck_frame = True

        if speed is not None:
            stuck_frame = speed <= self._params.speed_stuck_px_s

        if stuck_frame:
            self._consecutive_stuck += 1
            if self._consecutive_stuck == self._params.stuck_threshold:
                self._entered_at_ms = int(time.monotonic() * 1000)
        else:
            self._consecutive_stuck = 0
            self._entered_at_ms = None
        self._last_center = center
        self._last_distance = distance

    def reset(self) -> None:
        """重置检测器。"""
        self._consecutive_stuck = 0
        self._entered_at_ms = None
        self._last_center = None
        self._last_distance = None


class TargetEstimator:
    """估计器：锁定/追踪目标并输出 MovementState。"""

    def __init__(self, params: NavigationParams) -> None:
        self._params = params
        self.rotation = RotationAdjuster(enabled=params.rotation_adaptive_enabled)
        self.stuck = StuckDetector(params)

    def reset_target(self) -> None:
        """重置目标锁定与关联状态（切换目标/会话复位时调用）。"""
        self.rotation.reset()

    # ===== 锁定与追踪 =====

    def resolve_locked_target(
        self,
        locked: Optional[LockedTarget],
        targets: List[TargetInfo],
        selector,
    ) -> Tuple[Optional[LockedTarget], bool]:
        """解析锁定目标。

        返回值:
        - (锁定目标或 None, 是否发生目标切换)
        - 锁定存在：IOU+中心距+分数匹配追踪；miss 未超时返回旧位置占位
        - 无锁定：selector 选出新目标并生成新 lock_id
        """
        if locked is not None:
            tracked = self._track_locked_target(locked, targets)
            if tracked is not None:
                return tracked, False
            locked.miss_count += 1
            if locked.miss_count < self._params.target_lock_timeout:
                # 锁定丢失帧：返回旧位置占位（distance 置 None 触发距离缺失分支）
                lost = LockedTarget(
                    lock_id=locked.lock_id,
                    template=locked.template,
                    bbox=locked.bbox,
                    center=locked.center,
                    score=0.0,
                    distance=None,
                    miss_count=locked.miss_count,
                )
                return lost, False
            locked = None

        chosen = selector.select(targets)
        if chosen is None:
            return None, False
        new_locked = LockedTarget(
            lock_id=LockedTarget.generate_lock_id(chosen.template),
            template=chosen.template,
            bbox=chosen.bbox,
            center=chosen.center,
            score=chosen.score,
            distance=chosen.distance,
        )
        return new_locked, True

    def _track_locked_target(
        self,
        locked: LockedTarget,
        targets: List[TargetInfo],
    ) -> Optional[LockedTarget]:
        """在同模板候选中按 IOU+中心距追踪锁定目标。"""
        candidates = [
            t
            for t in targets
            if t.template == locked.template
            and t.score >= self._params.target_lock_score_threshold
        ]
        best: Optional[TargetInfo] = None
        best_iou = 0.0
        for candidate in candidates:
            iou = locked.iou(candidate.bbox)
            if iou < best_iou:
                continue
            cx, cy = candidate.center
            lx, ly = locked.center
            if math.hypot(cx - lx, cy - ly) > self._params.target_lock_center_tolerance:
                continue
            if iou < self._params.target_lock_iou_threshold:
                continue
            best, best_iou = candidate, iou
        if best is None:
            return None
        return LockedTarget(
            lock_id=locked.lock_id,
            template=locked.template,
            bbox=best.bbox,
            center=best.center,
            score=best.score,
            distance=best.distance,
            miss_count=0,
        )

    # ===== 帧状态估计 =====

    def estimate(
        self,
        state: MovementState,
        last_direction: Optional[str],
    ) -> MovementState:
        """基于当前 target/distance 更新方向、偏差、转向分级与死区判定。"""
        target = state.target
        if target is None:
            state.direction = None
            state.offset = (0.0, 0.0)
            state.offset_norm = 0.0
            state.deviation = 180.0
            state.turn_grade = TurnGrade.LARGE_TURN
            state.in_dead_zone = False
            state.target_angle = None
            return state

        tx, ty = target.center
        cx, cy = SCREEN_CENTER
        offset = (tx - cx, ty - cy)
        offset_norm = math.hypot(*offset)
        angle = compute_target_angle(target.center)

        state.offset = offset
        state.offset_norm = offset_norm
        state.deviation = deviation_angle(target.center)
        state.target_angle = angle
        state.in_dead_zone = offset_norm <= self._params.dead_zone
        state.turn_grade = classify_turn(
            state.deviation,
            self._params.rotation_lower_threshold,
            self._params.rotation_upper_threshold,
        )

        if state.in_dead_zone:
            state.direction = "forward"
        else:
            state.direction = self._apply_hysteresis(angle, last_direction)
        return state

    def _apply_hysteresis(
        self,
        angle: float,
        last_direction: Optional[str],
    ) -> Optional[str]:
        """方向滞回：与上一方向中心角偏差在阈值内则维持上一方向。"""
        from .geometry import dir_center_angle

        binned = self._bin_direction(angle)
        if last_direction is not None:
            last_center = dir_center_angle(last_direction)
            if last_center is not None:
                if abs(angle_diff(angle, last_center)) <= self._params.direction_hysteresis:
                    return last_direction
        return binned

    @staticmethod
    def _bin_direction(angle: float) -> str:
        """角度分箱为 8 向（geometry.bin_direction 的转发）。"""
        from .geometry import bin_direction

        return bin_direction(angle)

    def adaptive_speed(self, deviation: float) -> float:
        """更新 EMA 并返回当前自适应转速系数。"""
        return self.rotation.update(
            deviation,
            self._params.rotation_lower_threshold,
            self._params.rotation_upper_threshold,
        )

    # ===== fast path ROI =====

    def resolve_fast_path_roi(
        self,
        state: MovementState,
        locked: Optional[LockedTarget],
    ) -> Optional[Tuple[int, int, int, int]]:
        """锁定目标存在时收缩 ROI（bbox+padding，与全屏 ROI 求交）。"""
        if not self._params.enable_locked_fast_path or locked is None:
            state.fast_path_roi = None
            return None
        if state.fast_path_miss_count >= self._params.fast_path_miss_limit:
            state.fast_path_roi = None
            return None
        x, y, w, h = locked.bbox
        pad = self._params.lock_roi_padding
        if state.distance is None:
            pad += self._params.fast_path_max_turn_padding
        roi = (
            max(0, int(x - pad)),
            max(0, int(y - pad)),
            int(w + pad * 2),
            int(h + pad * 2),
        )
        # 与全屏 ROI 求交
        fx, fy, fw, fh = self._params.roi
        ix1, iy1 = max(roi[0], fx), max(roi[1], fy)
        ix2, iy2 = min(roi[0] + roi[2], fx + fw), min(roi[1] + roi[3], fy + fh)
        if ix2 <= ix1 or iy2 <= iy1:
            state.fast_path_roi = None
            return None
        state.fast_path_roi = (ix1, iy1, ix2 - ix1, iy2 - iy1)
        return state.fast_path_roi
