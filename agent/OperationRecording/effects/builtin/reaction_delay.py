# -*- coding: utf-8 -*-
"""
反应时间延迟效果插件

功能：
1. 在非瞬时动作执行前添加反应时间延迟
2. 模拟人类的反应延迟
"""
import random
from typing import Any, ClassVar, Dict, Optional

from ..base import EffectBase
from ..registry import register_effect


@register_effect("reaction_delay")
class ReactionDelayEffect(EffectBase):
    """反应时间延迟效果。

    在动作执行前添加反应时间延迟，模拟人类的反应延迟。
    仅对非瞬时动作生效。

    Config:
        min_ms: 反应时间最小值（毫秒），默认 80
        max_ms: 反应时间最大值（毫秒），默认 200
    """

    name: ClassVar[str] = "reaction_delay"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._min_ms: float = self._config.get("min_ms", 80)
        self._max_ms: float = self._config.get("max_ms", 200)

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
        return random.uniform(self._min_ms, self._max_ms) / 1000.0
