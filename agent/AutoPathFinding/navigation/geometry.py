# -*- coding: utf-8 -*-
"""
导航几何纯函数模块。

从旧 turn_strategy.py 移植并修复：
- 方向分箱扩展为 8 向（forward/backward/left/right + 四个斜向）
- classify_turn 改用"目标偏离屏幕中心的角度误差"分级，
  替换旧版"帧间角度差"实现（旧版两分支均返回 FINE_TUNE，属死代码）

所有函数均为纯函数，便于单元测试。
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Tuple

# 屏幕中心坐标（720p 基准）
SCREEN_CENTER = (640, 360)
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720

# 转向起止点裁剪条带（720p 基准 [x, y, w, h]）：
# 水平方向（左/右）用上方水平条带；垂直方向（上/下）用中央垂直条带。
# 单一事实来源放 geometry（policy 纯函数层也需引用），perception 转发再导出。
TURN_CLIP_HORIZONTAL: tuple[int, int, int, int] = (200, 80, 880, 120)
TURN_CLIP_VERTICAL: tuple[int, int, int, int] = (560, 60, 160, 600)

# 8 向方向名（与 OperationRecording 平台层 move/dodge 的方向词对齐：
# forward/backward/left/right + 斜向组合 "forward_left" 等）
DIRECTIONS_8: tuple[str, ...] = (
    "right",
    "forward_right",
    "forward",
    "forward_left",
    "left",
    "backward_left",
    "backward",
    "backward_right",
)

# 各 8 向方向的分箱中心角度（度，atan2(-dy, dx) 坐标系，right=0，forward=90）
DIR_CENTER_ANGLE_8: dict[str, float] = {
    "right": 0.0,
    "forward_right": 45.0,
    "forward": 90.0,
    "forward_left": 135.0,
    "left": 180.0,
    "backward_left": -135.0,
    "backward": -90.0,
    "backward_right": -45.0,
}


class TurnGrade(Enum):
    """转向分级：fine_tune 微调 / large_turn 大幅转向。"""

    FINE_TUNE = "fine_tune"
    LARGE_TURN = "large_turn"


def compute_target_angle(
    target_center: tuple[float, float],
    screen_center: tuple[int, int] = SCREEN_CENTER,
) -> float:
    """计算目标相对屏幕中心的角度（度，atan2(-dy, dx)，范围 [-180, 180]）。"""
    tx, ty = target_center
    cx, cy = screen_center
    dx = tx - cx
    dy = ty - cy
    if dx == 0 and dy == 0:
        return 0.0
    return math.degrees(math.atan2(-dy, dx))


def angle_diff(a: float, b: float) -> float:
    """返回 a 相对 b 的角度差（带环绕，范围 (-180, 180]）。"""
    return (a - b + 180.0) % 360.0 - 180.0


def bin_direction(angle: float) -> str:
    """将角度分箱为 8 向方向字符串（每 45° 一档）。

    参数:
    - angle: 角度（度），范围 [-180, 180]

    返回值:
    - str: DIRECTIONS_8 之一
    """
    # 以 right=0 为基准，扇区中心为 45° 的整数倍
    sector = math.floor((angle + 22.5) / 45.0) % 8
    return DIRECTIONS_8[sector]


def dir_center_angle(direction: str) -> float | None:
    """返回 8 向方向对应的分箱中心角度（度）。"""
    return DIR_CENTER_ANGLE_8.get(direction)


def deviation_angle(target_center: tuple[float, float]) -> float:
    """目标偏离屏幕中心的角度误差（度，绝对值 0~180）。

    0 表示目标恰在屏幕中心；90 表示目标在正侧方。
    """
    return abs(angle_diff(compute_target_angle(target_center), 0.0))


def classify_turn(
    deviation: float,
    lower_threshold: float,
    upper_threshold: float,
) -> TurnGrade:
    """按目标偏离中心的角度误差分级转向。

    修复旧版缺陷：旧版用帧间角度差且两分支都返回 FINE_TUNE，
    LARGE_TURN 几乎不可能触发。现以偏差角为准：
    - deviation < lower_threshold → FINE_TUNE
    - deviation >= upper_threshold → LARGE_TURN
    """
    if deviation >= upper_threshold:
        return TurnGrade.LARGE_TURN
    return TurnGrade.FINE_TUNE


def compute_turn_distance(
    offset_norm: float,
    turn_attempt: int,
    min_turn_distance: int,
    max_turn_distance: int,
    distance_missing_turn_scale: float,
    turn_min_floor_ratio: float,
    adaptive_speed: float = 1.0,
    speed_factor: float = 0.7,
) -> float:
    """计算转向滑动距离（像素）。

    设计：
    - 基础距离 = offset_norm * speed_factor（滑动后目标落在中心附近不越过）
    - 第 2 次起按 distance_missing_turn_scale 衰减
    - 上限 max_turn_distance / 下限 min_turn_distance * turn_min_floor_ratio 保护
    """
    base_distance = offset_norm * speed_factor
    if turn_attempt > 1:
        base_distance *= distance_missing_turn_scale ** (turn_attempt - 1)
    base_distance *= adaptive_speed
    if base_distance > max_turn_distance:
        base_distance = max_turn_distance
    floor = min_turn_distance * turn_min_floor_ratio
    if base_distance < floor:
        base_distance = floor
    return base_distance


def compute_turn_clip_rect(
    offset_x: float,
    offset_y: float,
    horizontal_clip: tuple[int, int, int, int],
    vertical_clip: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    """根据目标偏移主轴选择水平/垂直裁剪条带。"""
    if abs(offset_x) >= abs(offset_y):
        return horizontal_clip
    return vertical_clip


def compute_turn_coordinates(
    target_center: tuple[float, float],
    turn_attempt: int,
    *,
    min_turn_distance: int,
    max_turn_distance: int,
    distance_missing_turn_scale: float,
    turn_min_floor_ratio: float,
    horizontal_clip: tuple[int, int, int, int],
    vertical_clip: tuple[int, int, int, int],
    adaptive_speed: float = 1.0,
    min_offset_ratio: float = 0.0,
    screen_center: tuple[int, int] = SCREEN_CENTER,
    speed_factor: float = 0.7,
) -> Tuple[Tuple[int, int], Tuple[int, int]] | None:
    """基于目标中心偏移计算转向滑动起止点（swipe 方向 = -offset）。"""
    tx, ty = target_center
    cx, cy = screen_center
    offset_x = tx - cx
    offset_y = ty - cy
    offset_norm = math.hypot(offset_x, offset_y)

    min_offset = (SCREEN_WIDTH / 2) * min_offset_ratio
    if offset_norm < min_offset or offset_norm == 0:
        return None

    base_distance = compute_turn_distance(
        offset_norm,
        turn_attempt,
        min_turn_distance,
        max_turn_distance,
        distance_missing_turn_scale,
        turn_min_floor_ratio,
        adaptive_speed,
        speed_factor,
    )

    swx = -offset_x / offset_norm
    swy = -offset_y / offset_norm

    clip_x, clip_y, clip_w, clip_h = compute_turn_clip_rect(
        offset_x, offset_y, horizontal_clip, vertical_clip
    )
    rect_cx = clip_x + clip_w / 2
    rect_cy = clip_y + clip_h / 2

    half_dist = base_distance / 2
    start_x = rect_cx - swx * half_dist
    start_y = rect_cy - swy * half_dist
    end_x = rect_cx + swx * half_dist
    end_y = rect_cy + swy * half_dist

    start_x = max(clip_x, min(start_x, clip_x + clip_w))
    start_y = max(clip_y, min(start_y, clip_y + clip_h))
    end_x = max(clip_x, min(end_x, clip_x + clip_w))
    end_y = max(clip_y, min(end_y, clip_y + clip_h))

    if (int(start_x), int(start_y)) == (int(end_x), int(end_y)):
        return None

    return (int(start_x), int(start_y)), (int(end_x), int(end_y))


def compute_scan_turn_coordinates(
    step_px: float,
    sign: int,
    horizontal_clip: tuple[int, int, int, int],
) -> Tuple[Tuple[int, int], Tuple[int, int]] | None:
    """SEARCH 环视：水平条带内生成固定步长的转向滑动。

    参数:
    - step_px: 滑动像素距离（由 search_scan_step_deg × turn_px_per_deg 换算）
    - sign: +1 向右转（swipe 从右到左），-1 向左转
    """
    clip_x, clip_y, clip_w, clip_h = horizontal_clip
    cx = clip_x + clip_w / 2
    cy = clip_y + clip_h / 2
    half = min(step_px, clip_w) / 2
    if half < 1:
        return None
    start_x = cx + sign * half
    end_x = cx - sign * half
    start_x = max(clip_x, min(start_x, clip_x + clip_w))
    end_x = max(clip_x, min(end_x, clip_x + clip_w))
    if int(start_x) == int(end_x):
        return None
    return (int(start_x), int(cy)), (int(end_x), int(cy))


def compute_heading_turn_coordinates(
    turn_deg: float,
    horizontal_clip: tuple[int, int, int, int],
    turn_px_per_deg: float,
) -> Tuple[Tuple[int, int], Tuple[int, int]] | None:
    """P 控制转向：按目标转角（度）生成水平转向滑动。

    参数:
    - turn_deg: 需转角度，正=左转（swipe 从左到右），负=右转（swipe 从右到左）
    """
    step_px = abs(turn_deg) * turn_px_per_deg
    # 右转（负角）→ swipe 从右到左；左转（正角）→ swipe 从左到右
    sign = -1 if turn_deg >= 0 else 1
    return compute_scan_turn_coordinates(step_px, sign, horizontal_clip)

