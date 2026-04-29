# -*- coding: utf-8 -*-
"""
动作注册表，具有以下功能：
1. 注册/注销动作类
2. 获取动作类
3. 列出所有动作
4. 创建动作实例
"""

from typing import Dict, Type, Optional
from .base import ActionBase


class ActionRegistry:
    """
    动作注册表

    功能说明：
    1. 注册管理
       - register: 注册动作类
       - unregister: 注销动作类

    2. 查询获取
       - get_action: 获取动作类
       - list_actions: 列出所有动作

    3. 实例创建
       - create_action: 创建动作实例

    使用示例：
    >>> registry = ActionRegistry()
    >>> registry.register("move", MoveAction)
    >>> action = registry.create_action("move", platform)
    """

    def __init__(self):
        """
        初始化动作注册表

        执行流程：
        1. 创建空的动作字典
        """
        self._actions: Dict[str, Type[ActionBase]] = {}

    def register(self, action_name: str, action_class: Type[ActionBase]):
        """
        注册动作

        参数：
        - action_name: 动作名称
        - action_class: 动作类

        执行流程：
        1. 将动作类存入字典
        """
        self._actions[action_name] = action_class

    def unregister(self, action_name: str):
        """
        注销动作

        参数：
        - action_name: 动作名称

        执行流程：
        1. 检查动作是否存在
        2. 存在则删除
        """
        if action_name in self._actions:
            del self._actions[action_name]

    def get_action(self, action_name: str) -> Optional[Type[ActionBase]]:
        """
        获取动作类

        参数：
        - action_name: 动作名称

        返回值：
        - Type[ActionBase] | None: 动作类，不存在返回 None
        """
        return self._actions.get(action_name)

    def list_actions(self) -> list:
        """
        列出所有动作

        返回值：
        - list: 动作名称列表
        """
        return list(self._actions.keys())

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
        action_class = self.get_action(action_name)
        if action_class:
            return action_class(platform, context)
        return None


# 全局动作注册表实例
action_registry = ActionRegistry()
