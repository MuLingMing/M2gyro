# -*- coding: utf-8 -*-
"""
PathFinderAction 参数数据类

将执行器的 JSON 参数解析为类型安全的不可变对象，避免方法中反复使用裸 dict。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PathFinderParam:
    """
    PathFinderAction 执行参数

    Attributes:
        move_duration: 无距离信息时的默认移动时长（毫秒）
        move_duration_far: 距离 ≥ distance_far 时的移动时长（毫秒）
        move_duration_near: 距离 ≤ distance_near 时的移动时长（毫秒）
        distance_far: 远距离阈值（像素）
        distance_near: 近距离阈值（像素）
    """

    move_duration: int
    move_duration_far: int
    move_duration_near: int
    distance_far: int
    distance_near: int
