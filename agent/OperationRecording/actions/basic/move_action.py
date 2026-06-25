# -*- coding: utf-8 -*-
"""
移动动作，具有以下功能：
1. 支持四个方向移动
2. 支持持续时间控制
3. 参数验证
"""

from typing import Dict, Any
from ..base import ActionBase, TimelineMeta
from .. import register_action


@register_action("move")
class MoveAction(ActionBase):
    """
    移动动作

    功能说明：
    1. 方向控制
       - forward: 向前移动
       - backward: 向后移动
       - left: 向左移动
       - right: 向右移动

    2. 时间控制
       - duration: 持续时间，单位秒

    参数格式：
    {
        "action": "move",
        "params": {
            "direction": "forward",
            "duration": 1.0
        }
    }

    字段说明：
    - direction: 移动方向，可选值为 forward/backward/left/right，默认 forward
    - duration: 持续时间，单位秒，默认 1.0，必须 >= 0
    """

    timeline_meta = TimelineMeta(
        has_duration=True,
        release_method="move",
        smooth_transition=True,
    )

    def execute(self, params: Dict[str, Any]) -> bool:
        """
        执行动作

        参数：
        - params: 动作参数，包含 direction 和 duration

        返回值：
        - bool: 是否成功

        执行流程：
        1. 获取方向参数（默认 forward）
        2. 获取持续时间参数（默认 1.0）
        3. 调用平台 move 方法
        4. 返回执行结果
        """
        direction = params.get("direction", "forward")
        duration = params.get("duration", 1.0)
        return self._platform.move(direction, duration)

    def start(self, params: Dict[str, Any]) -> bool:
        """
        时间线模式：按下摇杆（不松开）

        参数：
        - params: 动作参数，包含 direction

        返回值：
        - bool: 是否成功
        """
        direction = params.get("direction", "forward")
        return self._platform.move(direction, 0)

    # 支持的移动方向：4 基本方向 + 4 组合方向（与 touch.py _get_joystick_directions 一致）
    _ALLOWED_DIRECTIONS = frozenset({
        "forward", "backward", "left", "right",
        "forward_left", "forward_right",
        "backward_left", "backward_right",
    })

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """
        验证参数

        参数：
        - params: 动作参数

        返回值：
        - bool: 参数是否有效

        验证规则：
        1. direction 必须在指定范围内
        2. duration 必须 >= 0
        """
        direction = params.get("direction", "forward")
        if direction not in self._ALLOWED_DIRECTIONS:
            return False
        duration = params.get("duration", 0)
        return isinstance(duration, (int, float)) and duration >= 0
