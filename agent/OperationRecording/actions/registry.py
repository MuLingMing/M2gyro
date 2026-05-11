# -*- coding: utf-8 -*-
"""
动作注册表，具有以下功能：
1. 注册/注销动作类
2. 获取动作类
3. 列出所有动作
4. 创建动作实例
5. 提供装饰器注册动作

继承自 ModuleRegistry 泛型基类，实现统一的模块注册接口。
"""

from typing import Optional
from .base import ActionBase
from ..registry import ModuleRegistry


class ActionRegistry(ModuleRegistry[ActionBase]):
    """
    动作注册表

    继承自 ModuleRegistry[ActionBase]，提供统一的模块注册接口。

    功能说明：
    1. 注册管理（继承自 ModuleRegistry）
       - register: 注册动作类
       - unregister: 注销动作类

    2. 查询获取（继承自 ModuleRegistry）
       - get: 获取动作类
       - list_modules: 列出所有动作
       - has: 检查动作是否存在

    3. 实例创建（扩展）
       - create_action: 创建动作实例（支持 platform 和 context 参数）

    使用示例：
    >>> registry = ActionRegistry()
    >>> registry.register("move", MoveAction)
    >>> action = registry.create_action("move", platform)
    """

    def create_action(self, action_name: str, platform, context=None) -> Optional[ActionBase]:
        """
        创建动作实例

        参数：
        - action_name: 动作名称
        - platform: 平台实例
        - context: MAA Context 实例，可选

        返回值：
        - ActionBase | None: 动作实例，不存在返回 None

        执行流程：
        1. 获取动作类
        2. 如果存在，创建实例（传递 context）
        3. 返回实例或 None
        """
        action_class = self.get(action_name)
        if action_class:
            action = action_class(platform)
            if context is not None:
                action.set_context(context)
            return action
        return None


action_registry = ActionRegistry()


def register_action(name: str):
    """
    动作注册装饰器

    功能说明：
    1. 注册动作类到全局注册表
    2. 必须显式指定动作名称，与 @register_effect/@register_platform 一致

    参数：
    - name: 动作名称（必填）

    使用示例：
    >>> @register_action("move")
    ... class MoveAction(ActionBase):
    ...     pass

    执行流程：
    1. 将动作类注册到全局注册表
    2. 返回原始类
    """
    def decorator(cls):
        action_registry.register(name, cls)
        return cls
    return decorator
