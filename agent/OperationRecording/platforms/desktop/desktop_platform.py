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
        _action_key_map = {"move": ["W","A","S","D"], "crouch": ["C"], "melee_attack": ["MouseLeft"], "ranged_attack": ["MouseRight"]}
"""

from ..keyboard import KeyboardPlatform
from ..registry import register_platform


@register_platform("desktop")
class DesktopPlatform(KeyboardPlatform):
    """Windows 桌面平台

    按键配置从 config/desktop_buttons.json 加载，支持外部修改。
    所有业务方法由 KeyboardPlatform 默认实现提供。
    """

    _button_config_file = "desktop_buttons.json"

    def __init__(self, platform_controller, context=None):
        super().__init__(platform_controller, context=context)
        self._controller_type = "desktop"
