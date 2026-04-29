# -*- coding: utf-8 -*-
"""
动作抽象基类，具有以下功能：
1. 定义动作接口规范
2. 统一平台实例管理
3. 提供参数验证钩子
4. 支持 context 访问（用于需要执行节点的动作）
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from maa.context import Context
from ..platforms.base import PlatformBase


class ActionBase(ABC):
    """
    动作抽象基类

    功能说明：
    1. 接口规范
       - 所有动作必须实现 name 属性
       - 所有动作必须实现 execute 方法

    2. 平台管理
       - 存储平台实例
       - 提供统一的平台访问接口

    3. Context 管理
       - 存储 MAA Context 实例
       - 用于需要执行节点的动作（如 run_node）

    4. 参数验证
       - 提供 validate_params 钩子
       - 默认返回 True（不验证）

    子类实现要求：
    - name: 返回动作名称
    - execute(params): 执行动作，返回是否成功
    - validate_params(params): 可选，验证参数
    """

    def __init__(self, platform: PlatformBase, context: Optional[Context] = None):
        """
        初始化动作

        参数：
        - platform: 平台实例
        - context: MAA Context 实例，可选

        执行流程：
        1. 存储平台实例
        2. 存储 Context 实例（可选）
        """
        self._platform = platform
        self._context = context

    @property
    @abstractmethod
    def name(self) -> str:
        """
        动作名称

        返回值：
        - str: 动作名称
        """
        pass

    @abstractmethod
    def execute(self, params: Dict[str, Any]) -> bool:
        """
        执行动作

        参数：
        - params: 动作参数

        返回值：
        - bool: 是否成功

        执行流程：
        1. 验证参数（可选）
        2. 调用平台方法执行动作
        3. 返回执行结果
        """
        pass

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """
        验证参数

        参数：
        - params: 动作参数

        返回值：
        - bool: 参数是否有效

        备注：
        - 子类可以覆盖此方法
        - 默认返回 True，不验证
        """
        return True
