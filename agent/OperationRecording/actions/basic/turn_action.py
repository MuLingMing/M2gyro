# -*- coding: utf-8 -*-
"""
转向动作，具有以下功能：
1. 支持直接坐标滑动（避免角度转换失真）
2. 参数验证
"""

from typing import Dict, Any, List
from ..base import ActionBase, TimelineMeta
from .. import register_action


@register_action("turn")
class TurnAction(ActionBase):
    """
    转向动作

    功能说明：
    1. 坐标控制
       - start: 滑动起点 [x, y]（720p 基准）
       - end: 滑动终点 [x, y]（720p 基准）
       - duration: 滑动时长（秒，可选）

    参数格式：
    {
        "action": "turn",
        "params": {
            "start": [1000, 150],
            "end": [1210, 150]
        }
    }

    字段说明：
    - start: 起点坐标 [x, y]（720p），必填
    - end: 终点坐标 [x, y]（720p），必填
    - duration: 滑动时长（秒），可选，不填使用平台默认值
    """

    timeline_meta = TimelineMeta(has_duration=False)

    def execute(self, params: Dict[str, Any]) -> bool:
        """
        执行动作

        参数：
        - params: 动作参数，包含 start/end 和可选 duration

        返回值：
        - bool: 是否成功

        执行流程：
        1. 解析坐标参数
        2. 调用平台 turn 方法
        3. 返回执行结果
        """
        start: List[int] = params.get("start", [0, 0])
        end: List[int] = params.get("end", [0, 0])
        duration = params.get("duration")
        return self._platform.turn(int(start[0]), int(start[1]), int(end[0]), int(end[1]), duration)

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """
        验证参数

        参数：
        - params: 动作参数

        返回值：
        - bool: 参数是否有效

        验证规则：
        1. start/end 必须是长度为 2 的列表，元素为 int 或 float
        2. duration 可选，如果提供必须 >= 0
        """
        for key in ("start", "end"):
            val = params.get(key)
            if not isinstance(val, list) or len(val) != 2:
                return False
            if not all(isinstance(v, (int, float)) for v in val):
                return False
        duration = params.get("duration")
        if duration is not None and not isinstance(duration, (int, float)):
            return False
        return True
