# -*- coding: utf-8 -*-
"""
下蹲动作，具有以下功能：
1. 执行一次下蹲
2. 支持按住时间控制
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
       - 支持按住时间控制

    参数格式：
    {
        "action": "crouch",
        "params": {
            "duration": 1.0
        }
    }

    字段说明：
    - duration: 按住按键的时间（秒），默认 0.1
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
        - params: 动作参数，包含 duration

        返回值：
        - bool: 是否成功

        执行流程：
        1. 获取 duration 参数（默认 0.1）
        2. 调用平台 crouch 方法
        3. 返回执行结果
        """
        duration = params.get("duration", 0.1)
        return self._platform.crouch(duration)
