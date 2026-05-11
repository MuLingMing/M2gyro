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

    仅提供触控坐标映射，所有业务方法由 TouchPlatform 默认实现提供。
    """

    _touch_positions = {
        "joystick_center": {
            "x": 225,
            "y": 536,
            "contact": 0,
            "joystick_run_offset": -60,
        },
        "jump_button": {
            "x": 978,
            "y": 410,
            "contact": 1,
        },
        "sprint_button": {
            "x": 1203,
            "y": 363,
            "contact": 1,
        },
        "interact_button": {
            "x": 750,
            "y": 358,
            "contact": 2,
        },
        "spiral_leap_button": {
            "x": 1086,
            "y": 364,
            "contact": 1,
        },
        "view_control_center": {
            "x": 1000,
            "y": 150,
            "contact": 3,
        },
        "crouch_button": {
            "x": 74,
            "y": 644,
            "contact": 4,
        },
        "charge_attack_button": {
            "x": 1090,
            "y": 507,
            "contact": 1,
        },
    }

    _generic_contact = 8

    def __init__(self, platform_controller):
        super().__init__(platform_controller)
        self._controller_type = "adb"
