# -*- coding: utf-8 -*-
"""
平台模块

提供平台抽象基类和工厂类，支持 ADB 和 Win32 平台实现。
"""

from .base import PlatformBase
from .factory import PlatformFactory

__all__ = ["PlatformBase", "PlatformFactory"]
