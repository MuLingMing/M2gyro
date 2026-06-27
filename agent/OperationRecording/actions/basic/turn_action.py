# -*- coding: utf-8 -*-
"""
转向动作，具有以下功能：
1. 支持直接坐标滑动（避免角度转换失真）
2. 参数验证
"""

from typing import Dict, Any
from ..base import ActionBase, TimelineMeta
from .. import register_action


@register_action("turn")
class TurnAction(ActionBase):
    """
    转向动作

    功能说明：
    1. 坐标控制
       - start_x/start_y: 滑动起点（720p 基准）
       - end_x/end_y: 滑动终点（720p 基准）
       - duration: 滑动时长（毫秒，可选）

    参数格式：
    {
        "action": "turn",
        "params": {
            "start_x": 1000,
            "start_y": 150,
            "end_x": 1210,
            "end_y": 150
        }
    }

    字段说明：
    - start_x: 起点 X 坐标（720p），必填
    - start_y: 起点 Y 坐标（720p），必填
    - end_x: 终点 X 坐标（720p），必填
    - end_y: 终点 Y 坐标（720p），必填
    - duration: 滑动时长（毫秒），可选，不填使用平台默认值
    """

    timeline_meta = TimelineMeta(has_duration=False)

    def execute(self, params: Dict[str, Any]) -> bool:
        """
        执行动作

        参数：
        - params: 动作参数，包含 start_x/start_y/end_x/end_y 和可选 duration

        返回值：
        - bool: 是否成功

        执行流程：
        1. 获取坐标参数
        2. 调用平台 turn 方法
        3. 返回执行结果
        """
        start_x = int(params.get("start_x", 0))
        start_y = int(params.get("start_y", 0))
        end_x = int(params.get("end_x", 0))
        end_y = int(params.get("end_y", 0))
        duration = params.get("duration")
        return self._platform.turn(start_x, start_y, end_x, end_y, duration)

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """
        验证参数

        参数：
        - params: 动作参数

        返回值：
        - bool: 参数是否有效

        验证规则：
        1. start_x/start_y/end_x/end_y 必须是 int 或 float
        2. duration 可选，如果提供必须 >= 0
        """
        for key in ("start_x", "start_y", "end_x", "end_y"):
            val = params.get(key)
            if val is None or not isinstance(val, (int, float)):
                return False
        duration = params.get("duration")
        if duration is not None and not isinstance(duration, (int, float)):
            return False
        return True
