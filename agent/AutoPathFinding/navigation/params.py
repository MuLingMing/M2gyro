# -*- coding: utf-8 -*-
"""
导航参数定义（单一事实来源）。

合并旧 recognition/param.py 与 action/param.py，消除两份参数表的漂移风险。
JSON Schema（deps/tools/）应与本 dataclass 字段保持同步。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from typing import Any, List, Tuple, Union

from .geometry import SCREEN_HEIGHT, SCREEN_WIDTH


@dataclass
class NavigationParams:
    """NavigationController 全量参数。

    分组：
    - 感知（模板匹配 / OCR 距离）
    - 目标选择与锁定
    - 方向与死区
    - 转向（分级 / 坐标 / 自适应）
    - 运动执行（move/dodge 时长）
    - 卡住与超时（stuck_timeout_ms 在本版真实生效）
    """

    # ===== 感知 =====
    expected_templates: List[str] = field(default_factory=list)
    roi: Tuple[int, int, int, int] = (0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)
    threshold: float = 0.8
    selector_type: str = "priority"
    selector_priority: List[Any] = field(default_factory=list)
    distance_pattern: str = r"(\d+)米"
    distance_offset: Tuple[int, int, int, int] = (-26, -30, 47, 57)
    distance_threshold: float = 0.3

    # ===== 方向与死区 =====
    dead_zone: int = 50
    direction_hysteresis: float = 15.0

    # ===== 到达 =====
    arrival_distance: int = 30
    interact_on_arrive: bool = True

    # ===== 目标锁定 =====
    target_lock_timeout: int = 3
    target_lock_center_tolerance: int = 100
    target_lock_score_threshold: float = 0.75
    target_lock_iou_threshold: float = 0.3
    enable_locked_fast_path: bool = True
    lock_roi_padding: int = 200
    fast_path_max_turn_padding: int = 400
    fast_path_miss_limit: int = 3

    # ===== 转向 =====
    enable_turning: bool = True
    max_turn_attempts: int = 3
    min_turn_distance: int = 50
    max_turn_distance: int = 400
    distance_missing_turn_scale: float = 0.5
    turn_min_floor_ratio: float = 0.5
    turn_speed_factor: float = 0.7
    turn_duration_s: float = 0.2
    large_turn_release_s: float = 0.1
    rotation_lower_threshold: float = 8.0
    rotation_upper_threshold: float = 60.0
    rotation_adaptive_enabled: bool = True

    # ===== 运动执行 =====
    move_duration_s: float = 0.5
    move_duration_far_s: float = 1.5
    move_duration_near_s: float = 0.3
    distance_far: int = 200
    distance_near: int = 50
    max_move_time_s: float = 0.0
    dodge_at_start: str = "never"
    dodge_direction: str = "backward"
    dodge_follows_direction: bool = True
    dodge_release_s: float = 0.05

    # ===== 卡住与脱困 =====
    stuck_threshold: int = 3
    stuck_distance_tolerance: float = 5.0
    stuck_center_tolerance: float = 10.0
    stuck_timeout_ms: int = 10000
    recover_dodge_direction: str = "backward"
    recover_turn_step_px: int = 120

    # ===== 小地图自状态感知（第一档：朝向+速度，默认关闭待实机标定） =====
    enable_minimap: bool = False
    # 小地图 ROI（x,y,w,h，720p 基准；需实机截图标定）
    minimap_roi: Tuple[int, int, int, int] = (0, 0, 0, 0)
    minimap_border_margin: int = 4
    # HSV 清洗阈值：白色 UI（V 高且 S 低）/ 彩色图标 / 未探索暗区
    minimap_ui_v_min: int = 200
    minimap_ui_s_max: int = 60
    minimap_icon_diff_threshold: int = 30
    minimap_dark_v_max: int = 60
    # 玩家箭头：中心窗口比例 / 亮度下限 / 最小面积
    minimap_arrow_center_ratio: float = 0.4
    minimap_arrow_v_min: int = 180
    minimap_arrow_min_area: int = 12
    # 平滑与速度采样
    heading_ema_alpha: float = 0.5
    speed_ema_alpha: float = 0.4
    speed_min_dt_s: float = 0.016
    speed_max_dt_s: float = 0.5
    # 速度低于该值视为原地（卡住判据之一，px/s）
    speed_stuck_px_s: float = 2.0
    # 角度↔像素标定与 P 控制转向（MaaEnd-2 steering_controller 经验值）
    turn_px_per_deg: float = 7.9
    steer_kp: float = 0.3
    steer_deadband_deg: float = 2.6
    steer_max_deg_moving: float = 28.0
    steer_max_deg_in_place: float = 70.0
    # SEARCH 环视：固定步长与累计上限
    search_scan_step_deg: float = 30.0
    search_scan_deg: float = 360.0

    # ===== 兼容字段名映射（旧参数名 → 新字段，便于迁移） =====
    # 旧 move_*/max_move_time 均为毫秒语义，需 ×0.001 换算为秒
    _ALIASES = {
        "move_duration": ("move_duration_s", 0.001),
        "move_duration_far": ("move_duration_far_s", 0.001),
        "move_duration_near": ("move_duration_near_s", 0.001),
        "max_move_time": ("max_move_time_s", 0.001),
        "dodge_release_ms": ("dodge_release_s", 0.001),
        "turn_duration_ms": ("turn_duration_s", 0.001),
        "large_turn_release_ms": ("large_turn_release_s", 0.001),
    }

    @classmethod
    def from_dict(cls, raw: Union[str, dict, None]) -> "NavigationParams":
        """从 pipeline custom 参数构造（str/dict/None 均可）。"""
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                raw = {}
        if not isinstance(raw, dict):
            raw = {}

        aliases = cls._ALIASES
        kwargs: dict[str, Any] = {}
        valid = {f.name for f in fields(cls)}
        for key, value in raw.items():
            if key in aliases:
                alias = aliases[key]
                if isinstance(alias, tuple):
                    name, scale = alias
                    value = value * scale if isinstance(value, (int, float)) else value
                else:
                    name = alias
            else:
                name = key
            if name in valid:
                kwargs[name] = value

        params = cls(**kwargs)
        params.expected_templates = params._calculate_priority_order(
            params.expected_templates, params.selector_priority
        )
        return params

    def _calculate_priority_order(
        self,
        expected_templates: List[str],
        selector_priority: List[Any],
    ) -> List[str]:
        """按 selector_priority 重排模板顺序（索引或名称两种格式）。"""
        if not selector_priority:
            return list(expected_templates)
        if selector_priority and isinstance(selector_priority[0], int):
            return self._order_by_index(expected_templates, selector_priority)
        return self._order_by_name(expected_templates, selector_priority)

    @staticmethod
    def _order_by_index(
        expected_templates: List[str],
        selector_priority: List[Any],
    ) -> List[str]:
        ordered: List[str] = []
        remaining = list(range(len(expected_templates)))
        for idx in selector_priority:
            if isinstance(idx, int) and 0 <= idx < len(expected_templates):
                ordered.append(expected_templates[idx])
                if idx in remaining:
                    remaining.remove(idx)
        ordered.extend(expected_templates[i] for i in remaining)
        return ordered

    @staticmethod
    def _order_by_name(
        expected_templates: List[str],
        selector_priority: List[Any],
    ) -> List[str]:
        ordered: List[str] = []
        remaining = list(expected_templates)
        for name in selector_priority:
            if isinstance(name, str) and name in remaining:
                ordered.append(name)
                remaining.remove(name)
        ordered.extend(remaining)
        return ordered
