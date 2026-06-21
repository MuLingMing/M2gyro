# -*- coding: utf-8 -*-
"""
目标信息数据类型定义
"""

from dataclasses import dataclass


@dataclass
class TargetInfo:
    """
    识别到的目标信息

    Attributes:
        template: 匹配的模板名称
        center: 中心坐标 (x, y)
        bbox: 边界框 (x, y, w, h)
        score: 匹配置信度
        distance: 距离值（如果存在）
    """

    template: str
    center: tuple[float, float]
    bbox: tuple[int, int, int, int]
    score: float
    distance: int | None = None
