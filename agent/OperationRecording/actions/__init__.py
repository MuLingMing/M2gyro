# -*- coding: utf-8 -*-
"""
动作模块

包含所有预定义的动作类，通过 @register_action 装饰器自动注册。
"""

from .base import ActionBase
from .registry import ActionRegistry, action_registry
from .auto_register import register_action

# 导入 basic 和 advanced 模块以触发装饰器注册
from . import basic
from . import advanced

__all__ = [
    "ActionBase",
    "ActionRegistry",
    "action_registry",
    "register_action",
    "basic",
    "advanced",
]