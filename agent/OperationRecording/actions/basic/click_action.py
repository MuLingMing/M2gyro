# -*- coding: utf-8 -*-
"""
点击动作，具有以下功能：
1. 点击指定坐标
"""

from typing import Dict, Any
from ..base import ActionBase, TimelineMeta
from .. import register_action


@register_action("click")
class ClickAction(ActionBase):
    """
    点击动作

    功能说明：
    1. 点击指定坐标的瞬时动作

    参数格式：
    {
        "action": "click",
        "params": {
            "x": 640,
            "y": 360
        }
    }

    字段说明：
    - x: 目标X坐标
    - y: 目标Y坐标
    """

    timeline_meta = TimelineMeta(has_duration=False)

    def execute(self, params: Dict[str, Any]) -> bool:
        x = params.get("x", 0)
        y = params.get("y", 0)
        return self._platform.click(x, y)