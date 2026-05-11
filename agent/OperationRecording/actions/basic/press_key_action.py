# -*- coding: utf-8 -*-
"""
按键动作，具有以下功能：
1. 按压指定按键
2. 支持持续时间控制
"""

from typing import Dict, Any
from ..base import ActionBase, TimelineMeta
from .. import register_action


@register_action("press_key")
class PressKeyAction(ActionBase):
    """
    按键动作

    功能说明：
    1. 按压指定按键并保持指定时间
    2. 平台方法内部处理完整的按下-等待-释放生命周期

    参数格式：
    {
        "action": "press_key",
        "params": {
            "key": "W",
            "duration": 0.1
        }
    }

    字段说明：
    - key: 按键名称
    - duration: 按住时长（秒），默认 0.1
    """

    timeline_meta = TimelineMeta(has_duration=False)

    def execute(self, params: Dict[str, Any]) -> bool:
        key = params.get("key", "")
        duration = params.get("duration", 0.1)
        return self._platform.press_key(key, duration)