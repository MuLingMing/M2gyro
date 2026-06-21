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
]
