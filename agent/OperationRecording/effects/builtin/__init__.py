# -*- coding: utf-8 -*-
"""
内置效果插件模块

包含所有内置效果插件类，通过 @register_effect 装饰器自动注册。
"""

from .acceleration import AccelerationEffect
from .random_delay import RandomDelayEffect
from .human_timing import HumanTimingEffect
from .reaction_delay import ReactionDelayEffect
from .fatigue import FatigueEffect

__all__ = [
    "AccelerationEffect",
    "RandomDelayEffect",
    "HumanTimingEffect",
    "ReactionDelayEffect",
    "FatigueEffect",
]
