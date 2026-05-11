# -*- coding: utf-8 -*-
"""
桌面平台实现（Windows）

功能：
1. 提供 Windows 虚拟按键码映射
2. 继承 KeyboardPlatform 的所有默认实现

新增平台示例（Mac）：
    @register_platform("mac")
    class MacPlatform(KeyboardPlatform):
        _key_codes = {"W": 0x0D, "A": 0x00, ...}  # macOS keyCode
        _action_key_map = {"move": ["W","A","S","D"], "crouch": ["C"], "charge_attack": ["MouseLeft"]}
"""

from ..keyboard import KeyboardPlatform
from ..registry import register_platform


@register_platform("desktop")
class DesktopPlatform(KeyboardPlatform):
    """Windows 桌面平台

    仅提供 Windows 虚拟按键码映射，所有业务方法由 KeyboardPlatform 默认实现提供。
    """

    _key_codes = {
        "W": 0x57,
        "A": 0x41,
        "S": 0x53,
        "D": 0x44,
        "Space": 0x20,
        "Shift": 0x10,
        "F": 0x46,
        "Q": 0x51,
        "C": 0x43,
        "MouseLeft": 0x01,
    }

    _action_key_map = {
        "move": ["W", "A", "S", "D"],
        "charge_attack": ["MouseLeft"],
        "crouch": ["C"],
    }

    def __init__(self, platform_controller):
        super().__init__(platform_controller)
        self._controller_type = "desktop"
