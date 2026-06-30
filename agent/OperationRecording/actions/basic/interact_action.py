# -*- coding: utf-8 -*-
"""
交互动作，具有以下功能：
1. 支持交互类型选择
2. 默认交互类型
3. 支持持续时间控制（长按交互键）
"""

from typing import Any, Dict, Optional
from ..base import ActionBase, TimelineMeta
from .. import register_action


@register_action("interact")
class InteractAction(ActionBase):
    """
    交互动作

    功能说明：
    1. 交互类型
       - default: 默认交互（F 键）
       - GrapplingHook: 钩爪交互（T 键 / ADB: grappling_hook_button）
       - E_skill: E 技能（E 键 / ADB: e_skill_button）
       - Q_skill: Q 技能（R 键 / ADB: q_skill_button）
       - pet: 宠物交互（Z 键 / ADB: pet_button）

    2. 持续时间控制
       - duration > 0 时按住交互键指定时间后释放
       - 无 duration 时执行单次瞬时交互

    参数格式：
    {
        "action": "interact",
        "params": {
            "interaction_type": "Q_skill",
            "duration": 4.0
        }
    }

    或无参数：
    {
        "action": "interact",
        "params": {}
    }

    字段说明：
    - interaction_type: 交互类型，默认 "default"
    - duration: 按住交互键的时间（秒，可选），无则执行单次瞬时交互
    """

    timeline_meta = TimelineMeta(
        has_duration=True,
        release_method="interact",
    )

    # 交互类型 → 平台方法名映射
    _TYPE_METHOD_MAP = {
        "GrapplingHook": "grappling_hook",
        "E_skill": "e_skill",
        "Q_skill": "q_skill",
        "pet": "pet",
    }

    def __init__(self, platform):
        super().__init__(platform)
        self._interaction_type: str = "default"

    def execute(self, params: Dict[str, Any]) -> bool:
        """
        执行动作

        参数：
        - params: 动作参数，包含可选的 interaction_type 和 duration

        返回值：
        - bool: 是否成功

        执行流程：
        1. 获取交互类型参数（默认 "default"）
        2. 获取 duration 参数（默认 0.1，即单次瞬时交互）
        3. 根据类型分派到对应平台方法
        4. 返回执行结果
        """
        interaction_type = params.get("interaction_type", "default")
        duration = params.get("duration", 0.1)
        method_name = self._TYPE_METHOD_MAP.get(interaction_type)
        if method_name:
            method = getattr(self._platform, method_name, None)
            if method:
                return method(duration)
        return self._platform.interact(interaction_type, duration)

    def start(self, params: Dict[str, Any]) -> bool:
        """
        时间线模式：按下交互键（不松开）

        参数：
        - params: 动作参数，包含可选的 interaction_type

        返回值：
        - bool: 是否成功
        """
        self._interaction_type = params.get("interaction_type", "default")
        method_name = self._TYPE_METHOD_MAP.get(self._interaction_type)
        if method_name:
            method = getattr(self._platform, method_name, None)
            if method:
                return method(0)
        return self._platform.interact(self._interaction_type, 0)

    def stop(self, params: Optional[Dict[str, Any]] = None) -> bool:
        """
        时间线模式：释放交互键

        优先从 params 提取 interaction_type（来自原始 start 事件的 params），
        兜底使用 start 时缓存的 _interaction_type。

        参数：
        - params: 动作参数（可选）

        返回值：
        - bool: 是否成功
        """
        interaction_type = (params or {}).get("interaction_type") or self._interaction_type
        return self._platform.release_interact(interaction_type)
