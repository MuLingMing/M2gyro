# -*- coding: utf-8 -*-
"""
目标选择器抽象基类
"""

from abc import ABC, abstractmethod

from .types import TargetInfo


class TargetSelector(ABC):
    """
    目标选择器接口

    从识别到的目标列表中选择一个目标。

    使用方式：
        selector = PriorityTargetSelector(priority=["quest", "npc"])
        selected = selector.select(targets)
    """

    @abstractmethod
    def select(self, targets: list[TargetInfo]) -> TargetInfo | None:
        """
        从目标列表中选择一个目标

        Args:
            targets: 识别到的目标列表

        Returns:
            选定的目标，如果没有可选目标则返回 None
        """
        ...
