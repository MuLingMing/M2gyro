# -*- coding: utf-8 -*-
"""
效果插件基类

功能：
1. 定义效果插件的标准接口（apply/pre_action/post_action）
2. 提供效果开关控制
3. 支持配置驱动
"""

from abc import ABC, abstractmethod
from typing import Any, ClassVar, Dict, Optional


class EffectBase(ABC):
    """效果插件基类。

    所有效果插件需继承此类并实现 apply() 方法。
    通过 pre_action()/post_action() 提供动作执行前后的回调钩子。
    """

    name: ClassVar[str] = ""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._enabled = self._config.get("enabled", True)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    @property
    def config(self) -> Dict[str, Any]:
        return self._config

    @abstractmethod
    def apply(
        self,
        action_name: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """应用效果到动作参数。

        Args:
            action_name: 动作名称
            params: 原始参数（不应原地修改，需 copy 后返回）
            context: 上下文信息（duration, is_instant, is_timeline 等）

        Returns:
            处理后的参数
        """
        pass

    def pre_action(self, action_name: str, context: Dict[str, Any]) -> float:
        """动作执行前回调。

        返回预延迟时间（秒），由调用方负责应用延迟，
        而非在回调内部 time.sleep() 阻塞调用线程。

        Args:
            action_name: 动作名称
            context: 上下文信息

        Returns:
            预延迟时间（秒），0.0 表示无需延迟
        """
        return 0.0

    def post_action(self, action_name: str, context: Dict[str, Any]) -> None:
        """动作执行后回调。"""
        pass
