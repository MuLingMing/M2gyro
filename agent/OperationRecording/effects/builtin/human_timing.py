# -*- coding: utf-8 -*-
"""
类人时序效果插件

功能：
1. 为操作时长添加微小随机变化
2. 为等待时长添加微小随机变化
"""
import random
from typing import Any, ClassVar, Dict, Optional

from ..base import EffectBase
from ..registry import register_effect


@register_effect("human_timing")
class HumanTimingEffect(EffectBase):
    """类人时序效果。

    为操作时长和等待时长添加微小的随机变化，
    模拟人类操作的时间不确定性。

    Config:
        duration_variance: 时长变化比例，默认 0.1（±10%）
        wait_variance: 等待时长变化比例，默认 0.2（±20%）
        min_duration_ms: 最小时长阈值（毫秒），低于此值不调整，默认 10
    """

    name: ClassVar[str] = "human_timing"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._duration_variance: float = self._config.get("duration_variance", 0.1)
        self._wait_variance: float = self._config.get("wait_variance", 0.2)
        self._min_duration_ms: float = self._config.get("min_duration_ms", 10)

    def apply(
        self,
        action_name: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        modified = False
        result = params

        duration = context.get("duration", 0)
        if duration is not None and duration > 0:
            duration_ms = duration * 1000
            if duration_ms >= self._min_duration_ms:
                variance = random.uniform(
                    -self._duration_variance, self._duration_variance
                )
                new_duration_ms = max(0, duration_ms * (1 + variance))
                if new_duration_ms >= self._min_duration_ms:
                    result = result.copy()
                    result["duration"] = new_duration_ms / 1000.0
                    modified = True

        if not modified and "wait_ms" in params:
            wait_ms = params["wait_ms"]
            if wait_ms >= self._min_duration_ms:
                variance = random.uniform(
                    -self._wait_variance, self._wait_variance
                )
                new_wait_ms = max(0, wait_ms * (1 + variance))
                if new_wait_ms >= self._min_duration_ms:
                    result = result.copy()
                    result["wait_ms"] = new_wait_ms

        return result
