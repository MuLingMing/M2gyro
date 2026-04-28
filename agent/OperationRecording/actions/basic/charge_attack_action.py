# -*- coding: utf-8 -*-
"""
蓄力攻击动作，具有以下功能：
1. 支持蓄力时间控制
2. 支持坐标指定
3. 可选参数
"""

from typing import Dict, Any
from ..base import ActionBase
from .. import register_action


@register_action("charge_attack")
class ChargeAttackAction(ActionBase):
    """
    蓄力攻击动作

    功能说明：
    1. 蓄力控制
       - duration: 蓄力时间，单位秒

    2. 坐标控制
       - x: X 坐标（可选）
       - y: Y 坐标（可选）

    参数格式：
    {
        "action": "charge_attack",
        "params": {
            "duration": 1.0,
            "x": 100,
            "y": 200
        }
    }

    或简化版本：
    {
        "action": "charge_attack",
        "params": {
            "duration": 1.0
        }
    }

    字段说明：
    - duration: 蓄力时间，单位秒，默认 1.0
    - x: X 坐标，可选，可为 None
    - y: Y 坐标，可选，可为 None
    """

    @property
    def name(self) -> str:
        """
        动作名称

        返回值：
        - str: "charge_attack"
        """
        return "charge_attack"

    def execute(self, params: Dict[str, Any]) -> bool:
        """
        执行动作

        参数：
        - params: 动作参数，包含 duration, x, y

        返回值：
        - bool: 是否成功

        执行流程：
        1. 获取蓄力时间参数（默认 1.0）
        2. 获取 X 坐标参数（可选）
        3. 获取 Y 坐标参数（可选）
        4. 调用平台 charge_attack 方法
        5. 返回执行结果
        """
        duration = params.get("duration", 1.0)
        x = params.get("x")
        y = params.get("y")
        return self._platform.charge_attack(duration, x, y)
