# -*- coding: utf-8 -*-
"""
滑动动作，具有以下功能：
1. 执行滑动操作
2. 支持自定义起止坐标和持续时间
"""

from typing import Dict, Any
from ..base import ActionBase, TimelineMeta
from .. import register_action


@register_action("swipe")
class SwipeAction(ActionBase):
    """
    滑动动作

    功能说明：
    1. 执行从起点到终点的滑动操作
    2. 平台方法内部处理完整的滑动生命周期

    参数格式：
    {
        "action": "swipe",
        "params": {
            "start_x": 100,
            "start_y": 200,
            "end_x": 300,
            "end_y": 400,
            "duration": 0.5
        }
    }

    字段说明：
    - start_x: 起始X坐标
    - start_y: 起始Y坐标
    - end_x: 结束X坐标
    - end_y: 结束Y坐标
    - duration: 滑动持续时间（秒），默认 0.5
    """

    timeline_meta = TimelineMeta(has_duration=False)

    def execute(self, params: Dict[str, Any]) -> bool:
        start_x = params.get("start_x", 0)
        start_y = params.get("start_y", 0)
        end_x = params.get("end_x", 0)
        end_y = params.get("end_y", 0)
        duration = params.get("duration", 0.5)
        return self._platform.swipe(start_x, start_y, end_x, end_y, duration)