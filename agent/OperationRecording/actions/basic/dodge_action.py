# -*- coding: utf-8 -*-
"""
闪避动作，具有以下功能：
1. 支持四个方向闪避
2. 支持无方向闪避
3. 参数验证
"""

from typing import Dict, Any
from ..base import ActionBase
from .. import register_action


@register_action("dodge")
class DodgeAction(ActionBase):
    """
    闪避动作

    功能说明：
    1. 方向控制
       - forward: 向前闪避
       - backward: 向后闪避
       - left: 向左闪避
       - right: 向右闪避
       - None: 无方向闪避

    参数格式：
    {
        "action": "dodge",
        "params": {
            "direction": "forward"
        }
    }

    或无参数：
    {
        "action": "dodge",
        "params": {}
    }

    字段说明：
    - direction: 闪避方向，可选值为 forward/backward/left/right，可为空，无默认
    """

    @property
    def name(self) -> str:
        """
        动作名称

        返回值：
        - str: "dodge"
        """
        return "dodge"

    def execute(self, params: Dict[str, Any]) -> bool:
        """
        执行动作

        参数：
        - params: 动作参数，包含可选的 direction

        返回值：
        - bool: 是否成功

        执行流程：
        1. 获取方向参数（可为 None）
        2. 调用平台 dodge 方法
        3. 返回执行结果
        """
        direction = params.get("direction")
        return self._platform.dodge(direction)

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """
        验证参数

        参数：
        - params: 动作参数

        返回值：
        - bool: 参数是否有效

        验证规则：
        1. direction 可以为 None
        2. 如果不为 None，必须在指定范围内
        """
        direction = params.get("direction")
        if direction is not None:
            return direction in ["forward", "backward", "left", "right"]
        return True
