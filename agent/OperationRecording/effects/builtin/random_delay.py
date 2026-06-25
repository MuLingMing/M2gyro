# -*- coding: utf-8 -*-
"""
随机延迟效果插件

功能：
1. 为指定动作添加随机延迟参数
2. 非瞬时动作执行前添加间隔延迟
"""
import random
from typing import Any, ClassVar, Dict, List, Optional

from ..base import EffectBase
from ..registry import register_effect


@register_effect("random_delay")
class RandomDelayEffect(EffectBase):
    """随机延迟效果。

    为指定动作添加随机延迟参数，模拟人类操作的时间不确定性。
    对于非瞬时动作，在动作执行前添加间隔延迟。

    Config:
        actions: 触发此效果的动作列表，默认 ["jump"]
        min_ms: 随机延迟最小值（毫秒），默认 20
        max_ms: 随机延迟最大值（毫秒），默认 80
        gap_min_ms: 动作间隔最小值（毫秒），默认 30
        gap_max_ms: 动作间隔最大值（毫秒），默认 150
    """

    name: ClassVar[str] = "random_delay"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._actions: List[str] = self._config.get("actions", ["jump"])
        self._min_ms: float = self._config.get("min_ms", 20)
        self._max_ms: float = self._config.get("max_ms", 80)
        self._gap_min_ms: float = self._config.get("gap_min_ms", 30)
        self._gap_max_ms: float = self._config.get("gap_max_ms", 150)

    def apply(
        self,
        action_name: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        if action_name not in self._actions:
            return params
        params = params.copy()
        params["random_delay"] = random.uniform(self._min_ms, self._max_ms) / 1000.0
        return params

    def pre_action(self, action_name: str, context: Dict[str, Any]) -> float:
        is_instant = context.get("is_instant", True)
        if is_instant:
            return 0.0
        return random.uniform(self._gap_min_ms, self._gap_max_ms) / 1000.0
