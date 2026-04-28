# -*- coding: utf-8 -*-
"""
转向动作，具有以下功能：
1. 支持角度控制
2. 支持正负角度
3. 参数验证
"""

from typing import Dict, Any
from ..base import ActionBase
from .. import register_action


@register_action("turn")
class TurnAction(ActionBase):
    """
    转向动作

    功能说明：
    1. 角度控制
       - 正数：向右转
       - 负数：向左转
       - 0：不转向

    参数格式：
    {
        "action": "turn",
        "params": {
            "angle": 90.0
        }
    }

    字段说明：
    - angle: 转向角度，单位度，默认 0.0，支持 int 或 float
    """

    @property
    def name(self) -> str:
        """
        动作名称

        返回值：
        - str: "turn"
        """
        return "turn"

    def execute(self, params: Dict[str, Any]) -> bool:
        """
        执行动作

        参数：
        - params: 动作参数，包含 angle

        返回值：
        - bool: 是否成功

        执行流程：
        1. 获取角度参数（默认 0.0）
        2. 调用平台 turn 方法
        3. 返回执行结果
        """
        angle = params.get("angle", 0.0)
        return self._platform.turn(angle)

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """
        验证参数

        参数：
        - params: 动作参数

        返回值：
        - bool: 参数是否有效

        验证规则：
        1. angle 必须是 int 或 float
        """
        angle = params.get("angle")
        return isinstance(angle, (int, float))
