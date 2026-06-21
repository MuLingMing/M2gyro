# -*- coding: utf-8 -*-
"""
平台工厂

功能：
1. 检测控制器类型
2. 创建平台实例
3. 从配置初始化平台（带缓存）
4. 平台注册通过 @register_platform 装饰器自动完成

缓存策略（方案 A）：
- create_from_config 使用 WeakKeyDictionary 缓存 platform 实例
- 同一 controller 多次调用返回同一 platform 实例
- 避免高频调用（如 PathFinderAction 自循环）时的重复创建
- 保留 platform 内部状态（_active_contacts、_active_directions）
- 注意：platform 持有 controller 的强引用（self._controller），
  因此 controller 不会被 GC，缓存条目生命周期与进程一致
- 进程结束时由 Python GC 统一清理；测试/重连场景请调用 clear_cache()
- create_platform 不走缓存（用于绕过缓存的场景）
"""

import weakref
from typing import Optional

from .base import PlatformBase
from .registry import platform_registry


# Platform 缓存：key 为 controller（弱引用），value 为 platform
# 当 controller 被 GC 后，缓存条目自动从 WeakKeyDictionary 中移除
_platform_cache: "weakref.WeakKeyDictionary" = weakref.WeakKeyDictionary()


class PlatformFactory:
    """
    平台工厂

    功能说明：
    1. detect_platform: 检测控制器类型
    2. create_platform: 创建平台实例（无缓存）
    3. create_from_config: 从配置创建平台实例（带缓存）
    4. clear_cache: 清空 platform 缓存

    平台注册通过 @register_platform 装饰器自动完成：
    - @register_platform("desktop") → DesktopPlatform
    - @register_platform("adb") → AdbPlatform

    使用示例：
    >>> platform = PlatformFactory.create_platform("desktop", controller)
    >>> platform = PlatformFactory.create_from_config(config, controller)  # 首次创建
    >>> platform2 = PlatformFactory.create_from_config(config, controller)  # 命中缓存
    >>> assert platform is platform2
    """

    @classmethod
    def detect_platform(cls, controller) -> str:
        """
        检测控制器类型

        参数：
        - controller: MAA 控制器对象

        返回值：
        - str: 平台类型，"desktop" 或 "adb"

        执行流程：
        1. 尝试获取控制器名称
        2. 尝试获取控制器配置
        3. 根据名称或配置判断平台类型
        4. 默认返回 "adb"
        """
        controller_name = getattr(controller, "name", None)
        controller_config = getattr(controller, "config", None)

        if controller_name:
            name_lower = controller_name.lower()
            if "win32" in name_lower or "desktop" in name_lower:
                return "desktop"
            elif "adb" in name_lower or "android" in name_lower:
                return "adb"

        if controller_config:
            config_str = str(controller_config).lower()
            if "win32" in config_str or "desktop" in config_str:
                return "desktop"
            elif "adb" in config_str or "android" in config_str:
                return "adb"

        return "adb"

    @classmethod
    def create_platform(
        cls, platform_type: str, controller
    ) -> Optional[PlatformBase]:
        """
        创建平台实例（无缓存）

        参数：
        - platform_type: 平台类型
        - controller: MAA 控制器对象

        返回值：
        - PlatformBase | None: 平台实例，失败返回 None

        执行流程：
        1. 规范化平台类型名称
        2. 确保平台模块已导入（触发 @register_platform）
        3. 从注册表创建实例

        注意：此方法不走缓存，如需缓存请使用 create_from_config
        """
        normalized_type = platform_type.lower()
        if normalized_type == "win32":
            normalized_type = "desktop"

        return platform_registry.create(normalized_type, controller)

    @classmethod
    def create_from_config(
        cls, config: dict, controller
    ) -> Optional[PlatformBase]:
        """
        从配置创建平台实例（带缓存）

        参数：
        - config: 配置字典，可包含 platform_type 字段（可选，未提供则自动检测）
        - controller: MAA 控制器对象

        返回值：
        - PlatformBase | None: 平台实例，失败返回 None

        执行流程：
        1. 检查缓存（基于 controller 引用）
        2. 缓存命中直接返回
        3. 缓存未命中则检测类型 + 创建实例 + 缓存

        缓存策略：
        - 使用 WeakKeyDictionary，key 为 controller，value 为 platform
        - 同一 controller 多次调用返回同一 platform 实例
        - 注意：platform 持有 controller 强引用，所以 cache 不会自动收缩
        - 仅缓存成功的 platform 实例（None 不缓存）
        - 进程退出时由 Python GC 统一清理；测试/重连场景请用 clear_cache()
        """
        # 检查缓存
        cached = _platform_cache.get(controller)
        if cached is not None:
            return cached

        # 缓存未命中，创建新实例
        platform_type = config.get("platform_type")
        if not platform_type:
            platform_type = cls.detect_platform(controller)
        platform = cls.create_platform(platform_type, controller)

        # 缓存成功的实例（None 不缓存，保留重新创建的机会）
        if platform is not None:
            _platform_cache[controller] = platform

        return platform

    @classmethod
    def clear_cache(cls) -> None:
        """
        清空 platform 缓存

        主要用于测试或 controller 手动重建场景。
        """
        _platform_cache.clear()
