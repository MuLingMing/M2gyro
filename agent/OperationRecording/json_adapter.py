# -*- coding: utf-8 -*-
"""
JSON 适配器

将现有 Pipeline JSON 格式的操作列表转换为可组合动作节点树。

输入格式（时间线模式）：
[
    {"action": "move", "params": {"direction": "left", "duration": 4.2,
     "overlays": [{"action": "move", "params": {"direction": "forward", "duration": 0.65}, "at": 2}]}},
    {"action": "jump", "params": {"duration": 0.3}},
]

输出：ActionNode 树根节点（通常是 Sequence）

映射规则：
- 顶层序列 → Sequence
- overlay → Parallel(main, At(offset, overlay_action))
- wait → 仅推进时间，不产生节点
"""

from typing import Any, Dict, List, Optional

from .core.node import ActionNode, PrimitiveAction, Sequence, Parallel, AtOffset
from .actions import action_registry
from utils.logger import logger


class JsonAdapter:
    """
    JSON → ActionNode 树转换器

    将 Pipeline JSON 的两种格式（序列/单个操作）统一转换为节点树。
    """

    @staticmethod
    def from_sequence(sequence: List[Dict[str, Any]]) -> ActionNode:
        """
        将时间线序列转换为节点树

        参数：
        - sequence: 时间线序列数据列表

        返回：
        - ActionNode: 节点树根节点（Sequence 或单个 PrimitiveAction）
        """
        children: List[ActionNode] = []
        cumulative_duration = 0.0  # 累计时间，用于计算 until 参数

        for item in sequence:
            action_name: Optional[str] = item.get("action")
            if action_name is None:
                continue

            params: Dict[str, Any] = item.get("params", {}) or {}

            if action_name == "wait":
                # wait 仅推进时间，不产生节点
                # 用 PrimitiveAction("wait") 仅为了 total_duration 计算
                # 处理 until 参数：绝对时间点转换为相对等待时长
                until = params.get("until")
                if until is not None:
                    duration = max(0.0, float(until) - cumulative_duration)
                else:
                    duration = _parse_duration(item, params)
                children.append(PrimitiveAction("wait", duration=duration))
                cumulative_duration += duration
                continue

            node = JsonAdapter._build_action_node(action_name, params, item)
            if node is not None:
                children.append(node)
                cumulative_duration += node.total_duration()

        if len(children) == 0:
            return PrimitiveAction("wait", duration=0.0)
        if len(children) == 1:
            return children[0]
        return Sequence(children)

    @staticmethod
    def _build_action_node(
        action_name: str,
        params: Dict[str, Any],
        item: Dict[str, Any],
    ) -> Optional[ActionNode]:
        """
        构建单个动作节点（含 overlay 处理）

        参数：
        - action_name: 动作名称
        - params: 动作参数（来自 params 字段）
        - item: 原始序列项数据

        返回：
        - ActionNode | None: 动作节点，失败返回 None
        """
        action_cls = action_registry.get(action_name)
        has_duration = action_cls.timeline_meta.has_duration if action_cls else False
        smooth_transition = action_cls.timeline_meta.smooth_transition if action_cls else False
        duration = _parse_duration(item, params)

        # 剥离 overlays，避免泄漏到动作 params 中
        clean_params = {k: v for k, v in params.items() if k != "overlays"}

        main_node = PrimitiveAction(
            action_name=action_name,
            params=clean_params,
            duration=duration,
            has_duration=has_duration,
            smooth_transition=smooth_transition,
        )

        # 处理 overlay
        overlays_raw = params.get("overlays", item.get("overlays", []))
        if not overlays_raw or not isinstance(overlays_raw, list):
            return main_node

        overlay_nodes: List[ActionNode] = [main_node]
        for overlay in overlays_raw:
            overlay_action_name = overlay.get("action")
            if overlay_action_name is None:
                continue

            overlay_params: Dict[str, Any] = overlay.get("params", {}) or {}
            overlay_at: float = float(overlay.get("at", 0.0))
            overlay_action_cls = action_registry.get(overlay_action_name)
            overlay_has_duration = overlay_action_cls.timeline_meta.has_duration if overlay_action_cls else False

            overlay_duration = float(overlay_params.get("duration", overlay.get("duration", 0)))
            overlay_node = PrimitiveAction(
                action_name=overlay_action_name,
                params=overlay_params,
                duration=overlay_duration,
                has_duration=overlay_has_duration,
                smooth_transition=False,
            )

            if overlay_at > 0:
                overlay_node = AtOffset(overlay_at, overlay_node)

            overlay_nodes.append(overlay_node)

        return Parallel(overlay_nodes)

    @staticmethod
    def from_operations(operations_data: List[Dict[str, Any]]) -> ActionNode:
        """
        将普通操作列表转换为节点树（非时间线模式）

        参数：
        - operations_data: 操作数据列表

        返回：
        - ActionNode: Sequence 节点
        """
        children: List[ActionNode] = []
        for op_data in operations_data:
            action_name = op_data.get("action")
            if action_name is None:
                continue
            params: Dict[str, Any] = op_data.get("params", {}) or {}
            action_cls = action_registry.get(action_name)
            has_duration = action_cls.timeline_meta.has_duration if action_cls else False

            children.append(PrimitiveAction(
                action_name=action_name,
                params=params,
                has_duration=has_duration,
            ))

        return Sequence(children)


def _parse_duration(item: Dict[str, Any], params: Dict[str, Any]) -> float:
    """从 item 或 params 中解析 duration"""
    duration = params.get("duration", item.get("duration", 0.0))
    return float(duration) if isinstance(duration, (int, float)) else 0.0
