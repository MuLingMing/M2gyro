# -*- coding: utf-8 -*-
"""
交互动作，具有以下功能：
1. 支持交互类型选择
2. 默认交互类型
"""

from typing import Dict, Any
from ..base import ActionBase
from .. import register_action


@register_action("interact")
class InteractAction(ActionBase):
    """
    交互动作

    功能说明：
    1. 交互类型
       - default: 默认交互
       - 其他：平台定义的其他类型

    参数格式：
    {
        "action": "interact",
        "params": {
            "interaction_type": "default"
        }
    }

    或无参数：
    {
        "action": "interact",
        "params": {}
    }

    字段说明：
    - interaction_type: 交互类型，默认 "default"
    """

    @property
    def name(self) -> str:
        """
        动作名称

        返回值：
        - str: "interact"
        """
        return "interact"

    def execute(self, params: Dict[str, Any]) -> bool:
        """
        执行动作

        参数：
        - params: 动作参数，包含可选的 interaction_type

        返回值：
        - bool: 是否成功

        执行流程：
        1. 获取交互类型参数（默认 "default"）
        2. 调用平台 interact 方法
        3. 返回执行结果
        """
        interaction_type = params.get("interaction_type", "default")
        return self._platform.interact(interaction_type)
