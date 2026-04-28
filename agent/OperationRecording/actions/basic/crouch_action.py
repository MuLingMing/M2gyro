# -*- coding: utf-8 -*-
"""
下蹲动作，具有以下功能：
1. 执行一次下蹲
2. 无需参数
"""

from typing import Dict, Any
from ..base import ActionBase
from .. import register_action


@register_action("crouch")
class CrouchAction(ActionBase):
    """
    下蹲动作

    功能说明：
    1. 单次下蹲
       - 执行一次下蹲动作
       - 无需任何参数

    参数格式：
    {
        "action": "crouch",
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
        - str: "crouch"
        """
        return "crouch"

    def execute(self, params: Dict[str, Any]) -> bool:
        """
        执行动作

        参数：
        - params: 动作参数，无需使用

        返回值：
        - bool: 是否成功

        执行流程：
        1. 调用平台 crouch 方法
        2. 返回执行结果
        """
        return self._platform.crouch()
