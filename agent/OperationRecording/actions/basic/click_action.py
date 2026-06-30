# -*- coding: utf-8 -*-
"""
点击动作，具有以下功能：
1. 点击指定坐标
2. 支持长按指定坐标
"""

from typing import Any, Dict, Optional
from ..base import ActionBase, TimelineMeta
from .. import register_action


@register_action("click")
class ClickAction(ActionBase):
    """
    点击动作

    功能说明：
    1. 点击指定坐标的瞬时动作
    2. 长按指定坐标
       - duration > 0 时按住指定坐标指定时间后释放
       - 无 duration 时执行单次瞬时点击

    参数格式：
    {
        "action": "click",
        "params": {
            "x": 640,
            "y": 360,
            "duration": 2.0
        }
    }

    字段说明：
    - x: 目标X坐标
    - y: 目标Y坐标
    - duration: 按住时间（秒，可选），无则执行单次瞬时点击
    """

    timeline_meta = TimelineMeta(
        has_duration=True,
        release_method="generic_touch",
    )

    def __init__(self, platform):
        super().__init__(platform)
        self._x: int = 0
        self._y: int = 0

    def execute(self, params: Dict[str, Any]) -> bool:
        """
        执行动作

        参数：
        - params: 动作参数，包含 x, y 和可选的 duration

        返回值：
        - bool: 是否成功

        执行流程：
        1. 获取坐标参数
        2. 如果有 duration > 0，调用 touch_hold 长按
        3. 否则调用 click 单次点击
        """
        x = params.get("x", 0)
        y = params.get("y", 0)
        duration = params.get("duration")
        if duration is not None and duration > 0:
            return self._platform.touch_hold(x, y, duration)
        return self._platform.click(x, y)

    def start(self, params: Dict[str, Any]) -> bool:
        """
        时间线模式：按下屏幕坐标（不松开）

        参数：
        - params: 动作参数，包含 x, y

        返回值：
        - bool: 是否成功
        """
        self._x = params.get("x", 0)
        self._y = params.get("y", 0)
        return self._platform.touch_hold(self._x, self._y, 0)

    def stop(self, params: Optional[Dict[str, Any]] = None) -> bool:
        """
        时间线模式：释放屏幕触点

        参数：
        - params: 动作参数（可选）

        返回值：
        - bool: 是否成功
        """
        return self._platform.release_touch()
