# -*- coding: utf-8 -*-
"""
平台模块

支持不同的控制器类型（如 Win32、ADB）的操作映射。
使用 @register_platform 装饰器自动注册平台实现。
"""

from .base import PlatformBase
from .keyboard import KeyboardPlatform
from .touch import TouchPlatform
from .factory import PlatformFactory
from .registry import PlatformRegistry, platform_registry, register_platform
from . import desktop
from . import adb

__all__ = [
    "PlatformBase",
    "KeyboardPlatform",
    "TouchPlatform",
    "PlatformFactory",
    "PlatformRegistry",
    "platform_registry",
    "register_platform",
]
