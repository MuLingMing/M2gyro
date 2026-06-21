# -*- coding: utf-8 -*-
"""
按类型优先级 + 距离组合选择目标
"""

from .base import TargetSelector
from .types import TargetInfo


class CompositeTargetSelector(TargetSelector):
    """
    按类型优先级 + 距离组合选择目标

    先按类型优先级筛选，再在同类型中选择距离最近的目标。

    参数：
        type_priority: 类型优先级列表，从高到低排列

    示例：
        selector = CompositeTargetSelector(type_priority=["quest", "npc"])
        selected = selector.select(targets)
    """

    def __init__(self, type_priority: list[str]):
        self.type_priority = type_priority

    def select(self, targets: list[TargetInfo]) -> TargetInfo | None:
        if not targets:
            return None

        # 按类型优先级筛选
        for ptype in self.type_priority:
            typed = [t for t in targets if t.template == ptype]
            if typed:
                # 在同类型中选择距离最近的
                with_distance = [t for t in typed if t.distance is not None]
                if with_distance:
                    # 类型检查器无法推断类型收窄，使用显式比较
                    return min(with_distance, key=lambda t: t.distance if t.distance is not None else float('inf'))
                return typed[0]

        # 没有匹配类型时选择第一个
        return targets[0]
