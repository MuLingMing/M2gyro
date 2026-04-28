# -*- coding: utf-8 -*-
"""
等待动作，具有以下功能：
1. 等待指定时间（duration）
2. 等待到目标时间点（until，仅限时间线模式）
"""

from typing import Dict, Any
from ..base import ActionBase
from .. import register_action


@register_action("wait")
class WaitAction(ActionBase):
    """
    等待动作

    功能说明：
    1. 等待指定时间（duration）
       - 执行等待操作
       - 可自定义等待时长
    2. 等待到目标时间点（until，仅限时间线模式）
       - 等待到指定的时间线时间点
       - 如果当前时间已超过目标时间点，则不等待

    参数格式：
    {
        "action": "wait",
        "params": {"duration": 1.0}
    }
    
    或（时间线模式专用）：
    {
        "action": "wait",
        "params": {"until": 5.0}
    }

    字段说明：
    - duration: 等待时间（秒，默认 1.0）
    - until: 目标时间点（秒，相对于时间线开始，仅限时间线模式）
      - 如果提供了 until，则忽略 duration
      - 如果当前时间 >= until，则不等待
    """

    @property
    def name(self) -> str:
        """
        动作名称

        返回值：
        - str: "wait"
        """
        return "wait"

    def execute(self, params: Dict[str, Any]) -> bool:
        """
        执行动作

        参数：
        - params: 动作参数，包含 duration（until 在普通模式下不适用）

        返回值：
        - bool: 是否成功

        执行流程：
        1. 获取等待时间（默认 1.0）
           - 注意：until 参数在普通模式下不适用
        2. 调用平台 wait 方法
        3. 返回执行结果
        """
        duration = params.get("duration", 1.0)
        return self._platform.wait(duration)
