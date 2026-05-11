# -*- coding: utf-8 -*-
"""
平台工厂

功能：
1. 检测控制器类型
2. 创建平台实例
3. 从配置初始化平台

平台注册通过 @register_platform 装饰器自动完成，
不再需要硬编码 if-elif 分支。
"""

from typing import Optional
from .base import PlatformBase
from .registry import platform_registry


class PlatformFactory:
    """
    平台工厂

    功能说明：
    1. detect_platform: 检测控制器类型
    2. create_platform: 创建平台实例

    平台注册通过 @register_platform 装饰器自动完成：
    - @register_platform("desktop") → DesktopPlatform
    - @register_platform("adb") → AdbPlatform

    使用示例：
    >>> platform = PlatformFactory.create_platform("desktop", controller)
    >>> platform = PlatformFactory.create_from_config(config, controller)
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
        controller_name = getattr(controller, 'name', None)
        controller_config = getattr(controller, 'config', None)

        if controller_name:
            name_lower = controller_name.lower()
            if 'win32' in name_lower or 'desktop' in name_lower:
                return "desktop"
            elif 'adb' in name_lower or 'android' in name_lower:
                return "adb"

        if controller_config:
            config_str = str(controller_config).lower()
            if 'win32' in config_str or 'desktop' in config_str:
                return "desktop"
            elif 'adb' in config_str or 'android' in config_str:
                return "adb"

        return "adb"

    @classmethod
    def create_platform(cls, platform_type: str, controller) -> Optional[PlatformBase]:
        """
        创建平台实例

        参数：
        - platform_type: 平台类型
        - controller: MAA 控制器对象

        返回值：
        - PlatformBase | None: 平台实例，失败返回 None

        执行流程：
        1. 规范化平台类型名称
        2. 确保平台模块已导入（触发 @register_platform）
        3. 从注册表创建实例
        """
        normalized_type = platform_type.lower()
        if normalized_type == "win32":
            normalized_type = "desktop"

        return platform_registry.create(normalized_type, controller)

    @classmethod
    def create_from_config(cls, config: dict, controller) -> Optional[PlatformBase]:
        """
        从配置创建平台实例

        参数：
        - config: 配置字典，需包含 platform_type 字段
        - controller: MAA 控制器对象

        返回值：
        - PlatformBase | None: 平台实例，失败返回 None

        执行流程：
        1. 检测平台类型
        2. 创建平台实例
        """
        platform_type = config.get("platform_type")
        if not platform_type:
            platform_type = cls.detect_platform(controller)
        return cls.create_platform(platform_type, controller)