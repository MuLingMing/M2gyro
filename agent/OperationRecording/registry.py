# -*- coding: utf-8 -*-
"""
统一模块注册表基类

提供泛型 ModuleRegistry[T] 基类，所有模块注册表（Action、Effect、Platform）
都继承此基类，实现统一的注册/注销/创建/查询接口。
"""

from typing import TypeVar, Generic, Type, Dict, Optional, List

T = TypeVar("T")


class ModuleRegistry(Generic[T]):
    """
    泛型模块注册表基类

    功能说明：
    1. 注册管理
       - register: 注册模块类
       - unregister: 注销模块类

    2. 查询获取
       - get: 获取模块类
       - list_modules: 列出所有模块
       - has: 检查模块是否存在

    3. 实例创建
       - create: 创建模块实例

    使用示例：
    >>> registry = ModuleRegistry[MyBase]()
    >>> registry.register("my_module", MyModule)
    >>> instance = registry.create("my_module", arg1, arg2)
    """

    def __init__(self) -> None:
        """
        初始化注册表

        执行流程：
        1. 创建空的模块字典
        """
        self._modules: Dict[str, Type[T]] = {}

    def register(self, name: str, cls: Type[T]) -> None:
        """
        注册模块

        参数：
        - name: 模块名称
        - cls: 模块类

        执行流程：
        1. 将模块类存入字典
        """
        self._modules[name] = cls

    def unregister(self, name: str) -> None:
        """
        注销模块

        参数：
        - name: 模块名称

        执行流程：
        1. 从字典中移除模块
        """
        self._modules.pop(name, None)

    def get(self, name: str) -> Optional[Type[T]]:
        """
        获取模块类

        参数：
        - name: 模块名称

        返回值：
        - Type[T] | None: 模块类，不存在返回 None
        """
        return self._modules.get(name)

    def create(self, name: str, *args, **kwargs) -> Optional[T]:
        """
        创建模块实例

        参数：
        - name: 模块名称
        - *args: 位置参数
        - **kwargs: 关键字参数

        返回值：
        - T | None: 模块实例，不存在返回 None

        执行流程：
        1. 获取模块类
        2. 如果存在，创建实例
        3. 返回实例或 None
        """
        cls = self.get(name)
        if cls is not None:
            return cls(*args, **kwargs)
        return None

    def list_modules(self) -> List[str]:
        """
        列出所有模块

        返回值：
        - List[str]: 模块名称列表
        """
        return list(self._modules.keys())

    def has(self, name: str) -> bool:
        """
        检查模块是否存在

        参数：
        - name: 模块名称

        返回值：
        - bool: 是否存在
        """
        return name in self._modules