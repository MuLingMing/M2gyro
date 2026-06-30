# -*- coding: utf-8 -*-
"""
按键动作，具有以下功能：
1. 按压指定按键
2. 支持持续时间控制
3. 支持长按按键（时间线模式）
"""

from typing import Any, Dict, Optional
from ..base import ActionBase, TimelineMeta
from .. import register_action


@register_action("press_key")
class PressKeyAction(ActionBase):
    """
    按键动作

    功能说明：
    1. 按压指定按键并保持指定时间
       - 平台方法内部处理完整的按下-等待-释放生命周期
    2. 长按按键（时间线模式）
       - start 时按下不松开，stop 时释放

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

    timeline_meta = TimelineMeta(
        has_duration=True,
        release_method="press_key",
    )

    def __init__(self, platform):
        super().__init__(platform)
        self._key: str = ""

    def execute(self, params: Dict[str, Any]) -> bool:
        """
        执行动作

        参数：
        - params: 动作参数，包含 key 和 duration

        返回值：
        - bool: 是否成功
        """
        key = params.get("key", "")
        duration = params.get("duration", 0.1)
        return self._platform.press_key(key, duration)

    def start(self, params: Dict[str, Any]) -> bool:
        """
        时间线模式：按下按键（不松开）

        参数：
        - params: 动作参数，包含 key

        返回值：
        - bool: 是否成功
        """
        self._key = params.get("key", "")
        return self._platform.hold_key(self._key, 0)

    def stop(self, params: Optional[Dict[str, Any]] = None) -> bool:
        """
        时间线模式：释放按键

        优先从 params 提取 key（来自原始 start 事件的 params），
        兜底使用 start 时缓存的 _key。

        参数：
        - params: 动作参数（可选）

        返回值：
        - bool: 是否成功
        """
        key = (params or {}).get("key") or self._key
        return self._platform.release_key(key)
