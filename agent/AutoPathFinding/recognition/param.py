# -*- coding: utf-8 -*-
"""
PathFindingReco 参数数据类

将识别器的 JSON 参数解析为类型安全的不可变对象，避免各方法中反复使用裸 dict。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PathFindingParam:
    """
    PathFindingReco 识别参数

    Attributes:
        ordered_templates: 按优先级排序后的模板列表
        roi: 识别区域 [x, y, w, h]
        threshold: 模板匹配阈值 [0, 1]
        selector_type: 选择器类型（priority/nearest/composite）
        distance_pattern: 距离 OCR 正则表达式
        distance_offset: 距离 OCR 区域偏移 [left, top, right, bottom]
        distance_threshold: OCR 置信度阈值
        dead_zone: 方向判断死区半径（像素，欧氏距离）
        arrival_distance: 判定为到达目标的距离阈值（像素）
        stuck_threshold: 连续多少帧无进展才判定为卡住
        stuck_distance_tolerance: 距离变化小于此值视为无进展
        stuck_center_tolerance: 目标中心偏移小于此值视为无进展
    """

    ordered_templates: list[str]
    roi: tuple[int, int, int, int]
    threshold: float
    selector_type: str
    distance_pattern: str
    distance_offset: list[int]
    distance_threshold: float
    dead_zone: int
    arrival_distance: int
    stuck_threshold: int
    stuck_distance_tolerance: int
    stuck_center_tolerance: int
