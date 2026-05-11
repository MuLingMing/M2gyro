# -*- coding: utf-8 -*-
"""
加速/减速效果插件

功能：
1. 为持续动作添加加速度/减速度标记
2. 动作开始前添加微小随机延迟
"""
import random
import time
from typing import Any, ClassVar, Dict, List, Optional

from ..base import EffectBase
from ..registry import register_effect


@register_effect("acceleration")
class AccelerationEffect(EffectBase):
    """加速/减速效果。

    为持续动作（如移动）添加加速度和减速度标记，
    使动作起止更自然。同时在动作开始前添加微小随机延迟。

    Config:
        actions: 触发此效果的动作列表，默认 ["move"]
        factor: 加速度因子，默认 0.15
    """

    name: ClassVar[str] = "acceleration"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._actions: List[str] = self._config.get("actions", ["move"])
        self._factor: float = self._config.get("factor", 0.15)

    def apply(
        self,
        action_name: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        if action_name not in self._actions:
            return params
        duration = context.get("duration", 0)
        if duration is not None and duration > 0:
            params = params.copy()
            params["acceleration"] = True
            params["deceleration"] = True
        return params

    def pre_action(self, action_name: str, context: Dict[str, Any]) -> None:
        if action_name not in self._actions:
            return
        delay = random.uniform(0.01, 0.05) * self._factor / 0.15
        time.sleep(delay)
