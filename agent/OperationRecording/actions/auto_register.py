# -*- coding: utf-8 -*-
"""
自动动作注册机制，具有以下功能：
1. 提供装饰器注册动作
2. 自动发现并注册动作
3. 简化为了兼容性保留
"""

from typing import Type, Optional
from .base import ActionBase
from .registry import action_registry


def register_action(name: Optional[str] = None):
    """
    动作注册装饰器

    功能说明：
    1. 注册动作类到全局注册表
    2. 支持自定义动作名称
    3. 默认使用类名去掉 Action 后缀的小写

    参数：
    - name: 动作名称，默认为类名的小写形式

    使用示例：
    >>> @register_action("move")
    ... class MoveAction(ActionBase):
    ...     pass

    执行流程：
    1. 获取动作名称（参数或从类名推导
    2. 注册到全局注册表
    """

    def decorator(cls: Type[ActionBase]):
        action_name = name or cls.__name__.replace('Action', '').lower()
        action_registry.register(action_name, cls)
        return cls
    return decorator
