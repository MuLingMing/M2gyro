# -*- coding: utf-8 -*-
"""
效果插件模块

包含效果插件基类、注册表、管理器和所有内置效果插件。
"""

from .base import EffectBase
from .registry import EffectRegistry, effect_registry, register_effect
from .manager import EffectManager
from . import builtin

__all__ = [
    "EffectBase",
    "EffectRegistry",
    "effect_registry",
    "register_effect",
    "EffectManager",
]
