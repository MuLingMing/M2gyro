# -*- coding: utf-8 -*-
"""
效果管理器

功能：
1. 统一调度所有效果插件
2. 支持全局开关和单插件开关
3. 在动作执行前后调用效果钩子
"""

from typing import Any, Dict, List, Optional

from .base import EffectBase
from .registry import effect_registry


class EffectManager:
    """效果插件管理器。

    统一调度所有已注册的效果插件，支持全局开关和单效果开关。
    可从配置字典批量加载效果插件。
    """

    def __init__(self) -> None:
        self._effects: List[EffectBase] = []
        self._enabled = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    def register(self, effect: EffectBase) -> None:
        self._effects.append(effect)

    def unregister(self, name: str) -> None:
        self._effects = [e for e in self._effects if e.name != name]

    def get_effect(self, name: str) -> Optional[EffectBase]:
        for effect in self._effects:
            if effect.name == name:
                return effect
        return None

    @property
    def effects(self) -> List[EffectBase]:
        return list(self._effects)

    def apply_effects(
        self,
        action_name: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not self._enabled:
            return params
        result = params.copy()
        for effect in self._effects:
            if effect.enabled:
                result = effect.apply(action_name, result, context)
        return result

    def pre_action(self, action_name: str, context: Dict[str, Any]) -> float:
        """动作执行前回调，汇总所有效果插件的预延迟。

        Returns:
            总预延迟时间（秒），0.0 表示无需延迟
        """
        if not self._enabled:
            return 0.0
        total_delay = 0.0
        for effect in self._effects:
            if effect.enabled:
                total_delay += effect.pre_action(action_name, context)
        return total_delay

    def post_action(self, action_name: str, context: Dict[str, Any]) -> None:
        if not self._enabled:
            return
        for effect in self._effects:
            if effect.enabled:
                effect.post_action(action_name, context)

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "EffectManager":
        """从配置字典创建 EffectManager 并加载所有效果插件。

        Args:
            config: effects 配置字典，格式如:
                {
                    "enabled": true,
                    "plugins": {
                        "acceleration": {"enabled": true, "actions": ["move"]},
                        ...
                    }
                }

        Returns:
            配置好的 EffectManager 实例
        """
        manager = cls()
        manager._enabled = config.get("enabled", True)
        plugins_config = config.get("plugins", {})
        for plugin_name, plugin_config in plugins_config.items():
            effect = effect_registry.create(plugin_name, plugin_config)
            if effect is not None:
                manager.register(effect)
        return manager
