# -*- coding: utf-8 -*-
"""
远程攻击动作，具有以下功能：
1. 支持持续时间控制
2. 支持坐标指定
3. 坐标默认通过 adb_buttons.json 中的 ranged_attack_button 配置
"""

from typing import Dict, Any
from ..base import ActionBase, TimelineMeta
from .. import register_action


@register_action("ranged_attack")
class RangedAttackAction(ActionBase):
    """
    远程攻击动作

    功能说明：
    1. 持续时间控制
       - duration: 按住时间，单位秒

    2. 坐标控制
       - x: X 坐标（可选）
       - y: Y 坐标（可选）
       未提供时默认使用配置文件中 ranged_attack_button 的坐标

    参数格式：
    {
        "action": "ranged_attack",
        "params": {
            "duration": 1.0,
            "x": 953,
            "y": 529
        }
    }

    或简化版本：
    {
        "action": "ranged_attack",
        "params": {
            "duration": 1.0
        }
    }

    字段说明：
    - duration: 按住时间，单位秒，默认 0.5
    - x: X 坐标，可选，可为 None
    - y: Y 坐标，可选，可为 None
    """

    timeline_meta = TimelineMeta(
        has_duration=True,
        release_method="ranged_attack",
    )

    def execute(self, params: Dict[str, Any]) -> bool:
        """
        执行动作

        参数：
        - params: 动作参数，包含 duration, x, y

        返回值：
        - bool: 是否成功

        执行流程：
        1. 获取持续时间参数（可选，未提供时使用平台默认值）
        2. 获取 X 坐标参数（可选）
        3. 获取 Y 坐标参数（可选）
        4. 调用平台 ranged_attack 方法
        5. 返回执行结果
        """
        duration = params.get("duration")
        x = params.get("x")
        y = params.get("y")
        return self._platform.ranged_attack(duration, x, y)

    def start(self, params: Dict[str, Any]) -> bool:
        """
        时间线模式：按下远程攻击（不松开）

        参数：
        - params: 动作参数，包含可选的 x, y

        返回值：
        - bool: 是否成功
        """
        x = params.get("x")
        y = params.get("y")
        return self._platform.ranged_attack(0, x, y)
