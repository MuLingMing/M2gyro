# -*- coding: utf-8 -*-
"""
按距离最近选择目标
"""

from .base import TargetSelector
from .types import TargetInfo


class NearestTargetSelector(TargetSelector):
    """
    按距离最近选择目标

    选择距离值最小的目标。只考虑有距离信息的目标。

    参数：
        fallback_to_first: 如果没有距离信息，是否选择第一个目标

    示例：
        selector = NearestTargetSelector()
        selected = selector.select(targets)
    """

    def __init__(self, fallback_to_first: bool = True):
        self.fallback_to_first = fallback_to_first

    def select(self, targets: list[TargetInfo]) -> TargetInfo | None:
        if not targets:
            return None

        # 过滤有距离信息的目标
        valid = [t for t in targets if t.distance is not None]

        if valid:
            # 类型检查器无法推断类型收窄，使用显式比较
            return min(valid, key=lambda t: t.distance if t.distance is not None else float('inf'))

        # 没有距离信息时的回退策略
        return targets[0] if self.fallback_to_first else None
