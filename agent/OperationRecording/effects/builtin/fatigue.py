# -*- coding: utf-8 -*-
"""
疲劳效果插件

功能：
1. 随动作次数增加反应时间
2. 超过阈值后反应时间线性增长
"""
import random
from typing import Any, ClassVar, Dict, Optional, Tuple

from ..base import EffectBase
from ..registry import register_effect


@register_effect("fatigue")
class FatigueEffect(EffectBase):
    """疲劳效果。

    随动作次数增加反应时间，模拟人类操作疲劳。
    超过阈值后，反应时间线性增长。

    Config:
        threshold: 开始疲劳的动作次数阈值，默认 10
        factor: 疲劳增长因子，默认 0.1
        base_min_ms: 基础反应时间最小值（毫秒），默认 80
        base_max_ms: 基础反应时间最大值（毫秒），默认 200
    """

    name: ClassVar[str] = "fatigue"
    MAX_REACTION_MS: ClassVar[float] = 2000

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._threshold: int = self._config.get("threshold", 10)
        self._factor: float = self._config.get("factor", 0.1)
        self._base_range: Tuple[float, float] = (
            self._config.get("base_min_ms", 80),
            self._config.get("base_max_ms", 200),
        )
        self._action_count: int = 0
        self._current_range: Tuple[float, float] = self._base_range

    def apply(
        self,
        action_name: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        return params

    def pre_action(self, action_name: str, context: Dict[str, Any]) -> float:
        is_instant = context.get("is_instant", True)
        if is_instant:
            return 0.0
        self._action_count += 1
        if self._action_count > self._threshold:
            self._update_reaction_time()
        return self._random_delay_ms(*self._current_range) / 1000.0

    def reset(self) -> None:
        self._action_count = 0
        self._current_range = self._base_range

    def _update_reaction_time(self) -> None:
        fatigue_level = (self._action_count - self._threshold) * self._factor
        min_ms = min(self._base_range[0] + fatigue_level * (
            self._base_range[1] - self._base_range[0]
        ), self.MAX_REACTION_MS)
        max_ms = min(self._base_range[1] + fatigue_level * (
            self._base_range[1] - self._base_range[0]
        ), self.MAX_REACTION_MS)
        self._current_range = (min_ms, max_ms)

    @staticmethod
    def _random_delay_ms(min_ms: float, max_ms: float) -> float:
        return random.uniform(min_ms, max_ms)
