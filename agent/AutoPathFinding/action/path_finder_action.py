# -*- coding: utf-8 -*-
"""
PathFinderAction —— 薄适配层（动作侧）。

仅做三件事：取 node_name 会话 → 读取识别侧缓存的 detail → 按序执行命令。
全部控制逻辑在 navigation 包内。

修复旧版缺陷：node_name 直接取自 RunArg.argv（旧版读不存在的
context.run_task_detail/tasker.current_node_name，永远回退固定名导致多节点共享状态）。
"""

from __future__ import annotations

from typing import Any, Dict

from maa.custom_action import CustomAction

from AutoPathFinding.navigation import controller


class PathFinderAction(CustomAction):
    """自动寻路动作（薄壳）。"""

    def run(
        self,
        context: Any,
        argv: "CustomAction.RunArg",
    ) -> bool:
        """动作回调：执行识别侧决策出的命令序列。"""
        node_name = getattr(argv, "node_name", None) or "PathFinderAction"
        session = controller.get(node_name)
        if session is None:
            return False
        detail: Dict = session.last_detail or {}
        try:
            return session.act(context, detail)
        except Exception:
            import traceback

            from utils.logger import logger

            logger.warning(
                "[PathFinderAction] act failed at %s:\n%s",
                node_name,
                traceback.format_exc(),
            )
            return False

    def stop(self) -> None:
        """停止回调：释放全部会话按键。"""
        controller.release_all_sessions()
