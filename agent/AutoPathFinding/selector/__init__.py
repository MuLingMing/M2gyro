# -*- coding: utf-8 -*-
"""
目标选择器模块

提供多种目标选择策略：
- PriorityTargetSelector: 按模板优先级选择
- NearestTargetSelector: 按距离最近选择
- CompositeTargetSelector: 按类型优先级 + 距离组合选择
"""

from .base import TargetSelector
from .priority_selector import PriorityTargetSelector
from .nearest_selector import NearestTargetSelector
from .composite_selector import CompositeTargetSelector
from .types import TargetInfo

__all__ = [
    "TargetSelector",
    "PriorityTargetSelector",
    "NearestTargetSelector",
    "CompositeTargetSelector",
    "TargetInfo",
    "create_selector",
]


def create_selector(
    selector_type: str = "priority",
    priority: list | None = None,
) -> TargetSelector:
    """按类型构造选择器。

    参数:
    - selector_type: priority / nearest / composite
    - priority: 模板优先级列表（priority/composite 模式使用）
    """
    priority = list(priority) if priority else []
    if selector_type == "nearest":
        return NearestTargetSelector(fallback_to_first=True)
    if selector_type == "composite":
        return CompositeTargetSelector(type_priority=priority)
    return PriorityTargetSelector(priority=priority)
