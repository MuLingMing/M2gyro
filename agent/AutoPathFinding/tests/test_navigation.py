# -*- coding: utf-8 -*-
"""navigation 包单元测试：geometry 纯函数 + policy 状态机 + params 解析。"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from AutoPathFinding.navigation.estimator import MovementState
from AutoPathFinding.navigation.geometry import (
    TurnGrade,
    bin_direction,
    classify_turn,
    compute_target_angle,
    deviation_angle,
)
from AutoPathFinding.navigation.params import NavigationParams
from AutoPathFinding.navigation.policy import CommandType, NavPhase, decide


def _state(**kw):
    base = dict(
        target=None,
        distance=None,
        direction=None,
        offset=(0.0, 0.0),
        offset_norm=0.0,
        deviation=0.0,
        in_dead_zone=False,
        turn_coordinates=None,
        turn_attempt=0,
        stuck_frames=0,
    )
    base.update(kw)
    return MovementState(**base)


class TestGeometry:
    def test_angle_right(self):
        # 目标在屏幕右侧 → 0°
        assert abs(compute_target_angle((900, 360))) < 1e-6

    def test_angle_forward(self):
        # 目标在屏幕上方（y 小）→ 90°
        assert abs(compute_target_angle((640, 100)) - 90.0) < 1e-6

    def test_bin_direction_8(self):
        assert bin_direction(0.0) == "right"
        assert bin_direction(90.0) == "forward"
        assert bin_direction(180.0) == "left"
        assert bin_direction(-90.0) == "backward"
        assert bin_direction(45.0) == "forward_right"
        assert bin_direction(-135.0) == "backward_left"

    def test_deviation_center_is_zero(self):
        assert deviation_angle((640, 360)) == 0.0

    def test_classify_turn_by_deviation(self):
        params = NavigationParams()
        # 修复验证：偏差角超 upper → LARGE_TURN（旧版永远 FINE_TUNE）
        assert (
            classify_turn(80.0, params.rotation_lower_threshold, params.rotation_upper_threshold)
            is TurnGrade.LARGE_TURN
        )
        assert (
            classify_turn(5.0, params.rotation_lower_threshold, params.rotation_upper_threshold)
            is TurnGrade.FINE_TUNE
        )


class TestPolicy:
    def test_arrive(self):
        params = NavigationParams(interact_on_arrive=True, arrival_distance=30)
        decision = decide(_state(distance=20), params, 0, 0, locked=True)
        assert decision.phase is NavPhase.ARRIVE
        assert decision.commands[0].type is CommandType.INTERACT

    def test_fail_on_stuck_timeout(self):
        # 修复验证：stuck_timeout_ms 真实生效
        params = NavigationParams(stuck_timeout_ms=10000)
        decision = decide(_state(distance=100), params, stuck_duration_ms=15000, elapsed_ms=20000, locked=True)
        assert decision.phase is NavPhase.FAIL

    def test_recover_when_stuck(self):
        params = NavigationParams(stuck_threshold=3)
        decision = decide(
            _state(distance=100, stuck_frames=3), params, 1000, 2000, locked=True
        )
        assert decision.phase is NavPhase.RECOVER
        assert decision.commands[0].type is CommandType.DODGE

    def test_search_no_target(self):
        params = NavigationParams()
        decision = decide(_state(), params, 0, 0, locked=False)
        assert decision.phase is NavPhase.SEARCH
        assert decision.commands[0].type is CommandType.MOVE

    def test_distance_missing_centered_moves_forward(self):
        params = NavigationParams()
        state = _state(distance=None, in_dead_zone=True, direction="forward")
        decision = decide(state, params, 0, 0, locked=True)
        assert decision.phase is NavPhase.APPROACH
        assert decision.commands[0].type is CommandType.MOVE
        assert decision.commands[0].direction == "forward"

    def test_distance_missing_offcenter_turns_only(self):
        params = NavigationParams()
        state = _state(
            distance=None,
            in_dead_zone=False,
            turn_coordinates=((700, 100), (580, 100)),
        )
        decision = decide(state, params, 0, 0, locked=True)
        assert decision.phase is NavPhase.TRACK
        assert all(c.type is CommandType.TURN for c in decision.commands)

    def test_approach_moves_with_interpolated_duration(self):
        params = NavigationParams(
            distance_far=200,
            distance_near=50,
            move_duration_far_s=1.5,
            move_duration_near_s=0.3,
        )
        state = _state(distance=125, in_dead_zone=True, direction="forward")
        decision = decide(state, params, 0, 0, locked=True)
        assert decision.phase is NavPhase.APPROACH
        move = decision.commands[-1]
        assert move.type is CommandType.MOVE
        # 125 在中点 → 时长约 (0.3+1.5)/2 = 0.9
        assert abs(move.duration_s - 0.9) < 0.01

    def test_offcenter_turns_then_moves(self):
        params = NavigationParams()
        state = _state(
            distance=100,
            in_dead_zone=False,
            direction="forward_right",
            turn_coordinates=((700, 100), (580, 100)),
        )
        decision = decide(state, params, 0, 0, locked=True)
        assert decision.phase is NavPhase.TRACK
        assert decision.commands[0].type is CommandType.TURN
        assert decision.commands[-1].type is CommandType.MOVE


class TestParams:
    def test_from_dict_alias_and_unit_scale(self):
        raw = {
            "expected_templates": ["b", "a"],
            "selector_priority": ["a", "b"],
            "turn_duration_ms": 200,
            "move_duration": 800,
        }
        params = NavigationParams.from_dict(raw)
        assert params.turn_duration_s == 0.2
        assert params.move_duration_s == 0.8
        assert params.expected_templates == ["a", "b"]

    def test_from_dict_invalid_json_string(self):
        params = NavigationParams.from_dict("not-json")
        assert params.expected_templates == []

    def test_from_dict_none(self):
        params = NavigationParams.from_dict(None)
        assert params.threshold == 0.8


class TestMinimap:
    """第一档小地图：合成图像验证朝向提取与速度（相位相关）。"""

    def _params(self, **kw) -> NavigationParams:
        base = dict(
            enable_minimap=True,
            minimap_roi=(0, 0, 200, 200),
            heading_ema_alpha=1.0,  # 单帧直读
            speed_min_dt_s=0.0,
            speed_max_dt_s=10.0,
        )
        base.update(kw)
        return NavigationParams(**base)

    def _frame(self, heading_deg: float, texture_shift: int = 0) -> "np.ndarray":
        import cv2
        import numpy as np

        img = np.zeros((200, 200, 3), np.uint8)
        # 已探索区：中灰带随机纹理（相位相关可检测位移）
        rng = np.random.default_rng(42)
        texture = rng.integers(90, 150, (200, 200), dtype=np.int16)
        texture = np.roll(texture, texture_shift, axis=1)
        img[:] = np.stack([texture] * 3, axis=-1).astype(np.uint8)
        # 未探索暗区环（v 低 → 清洗剔除，不干扰中心窗口）
        cv2.circle(img, (100, 100), 98, (40, 40, 40), 6)
        # 白色 UI 图标（应被剔除）
        cv2.circle(img, (40, 60), 6, (255, 255, 255), -1)
        # 玩家箭头：亮绿色细长三角（真实箭头为细长形，尖端离质心最远），尖端指向 heading_deg
        import math

        theta = math.radians(heading_deg)
        tip = (100 + 22 * math.cos(theta), 100 - 22 * math.sin(theta))
        left = (100 - 8 * math.sin(theta), 100 - 8 * math.cos(theta))
        right = (100 + 8 * math.sin(theta), 100 + 8 * math.cos(theta))
        cv2.fillConvexPoly(
            img, np.array([tip, left, right], np.int32), (0, 255, 0)
        )
        return img

    def test_heading_extraction(self):
        from AutoPathFinding.navigation.minimap import MinimapTracker

        for expected in (90.0, 0.0, 180.0, -90.0, 45.0):
            tracker = MinimapTracker(self._params())
            obs = tracker.update(self._frame(expected))
            assert obs.heading_valid, f"heading invalid at {expected}°"
            from AutoPathFinding.navigation.geometry import angle_diff

            assert abs(angle_diff(obs.heading_deg, expected)) <= 5.0

    def test_speed_positive_when_moving(self):
        import time

        from AutoPathFinding.navigation.minimap import MinimapTracker

        tracker = MinimapTracker(self._params())
        tracker.update(self._frame(90.0, texture_shift=0))
        time.sleep(0.05)  # 速度 = 位移/dt，需非零帧间隔
        obs = tracker.update(self._frame(90.0, texture_shift=12))
        assert obs.speed_valid
        assert obs.speed_px_s > 0

    def test_disabled_returns_invalid(self):
        from AutoPathFinding.navigation.minimap import MinimapTracker

        params = NavigationParams(enable_minimap=False)
        tracker = MinimapTracker(params)
        obs = tracker.update(self._frame(90.0))
        assert not obs.heading_valid and not obs.speed_valid


class TestMinimapPolicy:
    """朝向反馈接入 policy：有界 SEARCH 环视 + P 控制转向死区。"""

    def test_search_exhausted_fails(self):
        state = _state(
            heading=10.0,
            heading_valid=True,
            cumulative_turn_deg=400.0,
        )
        decision = decide(state, NavigationParams(), 0, 0, locked=False)
        assert decision.phase is NavPhase.FAIL
        assert decision.detail.get("search_exhausted") is True

    def test_search_scan_turn_bounded(self):
        state = _state(heading=10.0, heading_valid=True, cumulative_turn_deg=90.0)
        decision = decide(state, NavigationParams(), 0, 0, locked=False)
        assert decision.phase is NavPhase.SEARCH
        assert decision.commands[0].type is CommandType.TURN

    def test_steer_deadband_skips_turn(self):
        state = _state(
            distance=100,
            in_dead_zone=False,
            heading=90.0,
            heading_valid=True,
            target_angle=90.0,  # 已对准 → 死区内不转
        )
        decision = decide(state, NavigationParams(), 0, 0, locked=True)
        types = [c.type for c in decision.commands]
        assert CommandType.TURN not in types
        assert decision.commands[-1].type is CommandType.MOVE

    def test_steer_generates_turn_command(self):
        state = _state(
            distance=100,
            in_dead_zone=False,
            heading=90.0,
            heading_valid=True,
            target_angle=45.0,  # 需右转 45°
        )
        decision = decide(state, NavigationParams(), 0, 0, locked=True)
        turn_cmds = [c for c in decision.commands if c.type is CommandType.TURN]
        assert turn_cmds, "应对准偏差生成转向命令"
        (sx, sy), (ex, ey) = turn_cmds[0].turn_coordinates
        # 右转 → swipe 从右到左（start_x > end_x）
        assert sx > ex
