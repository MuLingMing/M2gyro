# -*- coding: utf-8 -*-
"""
ADB 平台实现

功能：
1. 提供默认触控坐标映射
2. 继承 TouchPlatform 的所有默认实现

新增 ADB 变体示例：
    @register_platform("adb_variant")
    class AdbVariantPlatform(TouchPlatform):
        _touch_positions = {
            "joystick_center": {"x": 256, "y": 600, "contact": 0, "joystick_run_offset": -60},
            "jump_button": {"x": 1200, "y": 500, "contact": 1},
            ...
        }
        _generic_contact = 8
"""

from ..touch import TouchPlatform
from ..registry import register_platform


@register_platform("adb")
class AdbPlatform(TouchPlatform):
    """ADB 平台

    按钮配置从 config/adb_buttons.json 加载，支持外部修改。
    所有业务方法由 TouchPlatform 默认实现提供。
    """

    _button_config_file = "adb_buttons.json"

    def __init__(self, platform_controller):
        super().__init__(platform_controller)
        self._controller_type = "adb"
