# -*- coding: utf-8 -*-
"""
交互动作，具有以下功能：
1. 支持交互类型选择
2. 默认交互类型
"""

from typing import Dict, Any
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

    参数格式：
    {
        "action": "interact",
        "params": {
            "interaction_type": "default"
        }
    }

    或无参数：
    {
        "action": "interact",
        "params": {}
    }

    字段说明：
    - interaction_type: 交互类型，默认 "default"
    """

    timeline_meta = TimelineMeta(has_duration=False)

    def execute(self, params: Dict[str, Any]) -> bool:
        """
        执行动作

        参数：
        - params: 动作参数，包含可选的 interaction_type

        返回值：
        - bool: 是否成功

        执行流程：
        1. 获取交互类型参数（默认 "default"）
        2. 根据类型分派到对应平台方法
        3. 返回执行结果

        支持的交互类型：
        - default: 默认交互（F 键）
        - GrapplingHook: 钩爪交互（T 键）
        - E_skill: E 技能（E 键）
        - Q_skill: Q 技能（R 键）
        - pet: 宠物交互（Z 键）
        """
        interaction_type = params.get("interaction_type", "default")
        type_method_map = {
            "GrapplingHook": "grappling_hook",
            "E_skill": "e_skill",
            "Q_skill": "q_skill",
            "pet": "pet",
        }
        method_name = type_method_map.get(interaction_type)
        if method_name:
            method = getattr(self._platform, method_name, None)
            if method:
                return method()
        return self._platform.interact(interaction_type)
