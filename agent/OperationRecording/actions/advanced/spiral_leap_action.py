# -*- coding: utf-8 -*-
"""
螺旋飞跃动作，具有以下功能：
1. 执行一次螺旋飞跃
2. 无需参数
"""

from typing import Dict, Any
from ..base import ActionBase
from .. import register_action


@register_action("spiral_leap")
class SpiralLeapAction(ActionBase):
    """
    螺旋飞跃动作

    功能说明：
    1. 单次螺旋飞跃
       - 执行一次螺旋飞跃动作
       - 无需任何参数

    参数格式：
    {
        "action": "spiral_leap",
        "params": {}
    }

    字段说明：
    - params: 无需参数，可为空
    """

    @property
    def name(self) -> str:
        """
        动作名称

        返回值：
        - str: "spiral_leap"
        """
        return "spiral_leap"

    def execute(self, params: Dict[str, Any]) -> bool:
        """
        执行动作

        参数：
        - params: 动作参数，无需使用

        返回值：
        - bool: 是否成功

        执行流程：
        1. 调用平台 spiral_leap 方法
        2. 返回执行结果
        """
        return self._platform.spiral_leap()
