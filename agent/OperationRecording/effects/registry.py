# -*- coding: utf-8 -*-
"""
效果插件注册表

功能：
1. 注册/注销效果插件
2. 获取效果插件类
3. 列出所有效果
4. 创建效果实例

继承自 ModuleRegistry 泛型基类，实现统一的模块注册接口。
"""

from .base import EffectBase
from ..registry import ModuleRegistry


class EffectRegistry(ModuleRegistry[EffectBase]):
    """
    效果插件注册表

    继承自 ModuleRegistry[EffectBase]，提供统一的模块注册接口。

    功能说明：
    1. 注册管理（继承自 ModuleRegistry）
       - register: 注册效果插件
       - unregister: 注销效果插件

    2. 查询获取（继承自 ModuleRegistry）
       - get: 获取效果插件类
       - list_modules: 列出所有效果
       - has: 检查效果是否存在

    使用示例：
    >>> registry = EffectRegistry()
    >>> registry.register("acceleration", AccelerationEffect)
    >>> instance = registry.create("acceleration", config={"factor": 0.15})
    """


effect_registry = EffectRegistry()


def register_effect(name: str):
    """注册效果插件"""
    def decorator(cls: type):
        effect_registry.register(name, cls)
        return cls
    return decorator
