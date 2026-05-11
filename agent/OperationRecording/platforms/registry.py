# -*- coding: utf-8 -*-
"""
平台注册表

功能：
1. 注册/注销平台类
2. 获取平台类
3. 列出所有平台
4. 创建平台实例

继承自 ModuleRegistry 泛型基类，实现统一的模块注册接口。
"""

from .base import PlatformBase
from ..registry import ModuleRegistry


class PlatformRegistry(ModuleRegistry[PlatformBase]):
    """
    平台注册表

    继承自 ModuleRegistry[PlatformBase]，提供统一的模块注册接口。

    功能说明：
    1. 注册管理（继承自 ModuleRegistry）
       - register: 注册平台类
       - unregister: 注销平台类

    2. 查询获取（继承自 ModuleRegistry）
       - get: 获取平台类
       - list_modules: 列出所有平台
       - has: 检查平台是否存在

    使用示例：
    >>> registry = PlatformRegistry()
    >>> registry.register("desktop", DesktopPlatform)
    >>> instance = registry.create("desktop", controller)
    """


platform_registry = PlatformRegistry()


def register_platform(name: str):
    """注册平台"""
    def decorator(cls: type):
        platform_registry.register(name, cls)
        return cls
    return decorator
