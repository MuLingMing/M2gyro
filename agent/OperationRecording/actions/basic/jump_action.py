# -*- coding: utf-8 -*-
"""
跳跃动作，具有以下功能：
1. 执行一次跳跃
2. 支持持续时间控制（长按跳跃键）
"""

from typing import Dict, Any, Optional
from ..base import ActionBase, TimelineMeta
from .. import register_action


@register_action("jump")
class JumpAction(ActionBase):
    """
    跳跃动作

    功能说明：
    1. 单次跳跃
       - 执行一次跳跃动作
    2. 长按跳跃
       - duration > 0 时按住跳跃键指定时间后释放
       - 无 duration 时执行单次瞬时跳跃

    参数格式：
    {
        "action": "jump",
        "params": {
            "duration": 1.0
        }
    }

    或无参数：
    {
        "action": "jump",
        "params": {}
    }

    字段说明：
    - duration: 按住跳跃键的时间（秒，可选），无则执行单次跳跃
    """

    timeline_meta = TimelineMeta(
        has_duration=True,
        release_method="jump_button",
    )

    def execute(self, params: Dict[str, Any]) -> bool:
        """
        执行动作

        参数：
        - params: 动作参数，包含可选的 duration

        返回值：
        - bool: 是否成功

        执行流程：
        1. 获取 duration 参数（默认 0.1，即单次瞬时跳跃）
        2. 调用平台 jump 方法
        3. 返回执行结果
        """
        duration = params.get("duration", 0.1)
        return self._platform.jump(duration)

    def start(self, params: Dict[str, Any]) -> bool:
        """
        时间线模式：按下跳跃键（不松开）

        参数：
        - params: 动作参数（未使用）

        返回值：
        - bool: 是否成功
        """
        return self._platform.jump(0)

    def stop(self, params: Optional[Dict[str, Any]] = None) -> bool:
        """
        时间线模式：释放跳跃键

        参数：
        - params: 动作参数（可选）

        返回值：
        - bool: 是否成功
        """
        return self._platform.release_action("jump_button")
