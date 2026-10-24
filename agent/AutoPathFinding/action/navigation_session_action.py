# -*- coding: utf-8 -*-
"""
PathFindingInit / PathFindingRelease —— 导航会话生命周期管理 Action。

Pipeline 用法：
- 任务开始: {"action": "PathFindingInit", "custom_action_param": {...NavigationParams...}}
- 导航循环: PathFindingReco + PathFinderAction 节点（next 含 arrive/fail 分支）
- 任务结束: {"action": "PathFindingRelease"}

node_name 区分不同导航节点（各节点独立会话，互不串状态）。
"""

from __future__ import annotations

from typing import Any

from maa.custom_action import CustomAction

from AutoPathFinding.navigation import NavigationParams, controller
from utils.logger import logger


class PathFindingInit(CustomAction):
    """创建/重置导航会话（任务开始时调用）。"""

    def run(
        self,
        context: Any,
        argv: "CustomAction.RunArg",
    ) -> bool:
        """按 node_name 创建（或重置）会话并应用参数。"""
        node_name = getattr(argv, "node_name", None) or "PathFindingInit"
        params = NavigationParams.from_dict(argv.custom_action_param)
        session = controller.create(node_name, params)
        logger.info(
            "[PathFindingInit] session ready: %s (templates=%s)",
            node_name,
            params.expected_templates,
        )
        return True


class PathFindingRelease(CustomAction):
    """释放导航会话（任务结束/中断时调用，兜底松键）。"""

    def run(
        self,
        context: Any,
        argv: "CustomAction.RunArg",
    ) -> bool:
        """释放 node_name 会话；custom_action_param 为 all 时释放全部。"""
        raw = argv.custom_action_param or {}
        if isinstance(raw, str):
            import json as _json

            try:
                raw = _json.loads(raw)
            except _json.JSONDecodeError:
                raw = {}
        if isinstance(raw, dict) and raw.get("all"):
            count = controller.release_all_sessions()
            logger.info("[PathFindingRelease] released all sessions: %d", count)
            return True
        node_name = getattr(argv, "node_name", None) or "PathFindingRelease"
        ok = controller.release(node_name)
        logger.info("[PathFindingRelease] release %s: %s", node_name, ok)
        return True
