# -*- coding: utf-8 -*-
"""
PathFindingReco —— 薄适配层（识别侧）。

仅做三件事：解析参数 → 取 node_name 会话 → 调 NavigationSession.perceive。
全部控制逻辑在 navigation 包内（详见 navigation/controller.py）。

pipeline 用法（custom_recognition_param 透传 NavigationParams 字段）:
    {"recognition": "PathFindingReco", "action": "PathFinderAction",
     "custom_recognition_param": {"expected_templates": ["目标文件夹"], ...}}
detail.phase 可供 next 分支: arrive / fail / approach / track / search / recover
"""

from __future__ import annotations

from typing import Any, Tuple

from maa.custom_recognition import CustomRecognition

from AutoPathFinding.navigation import NavigationParams, controller


class PathFindingReco(CustomRecognition):
    """自动寻路识别（薄壳）。"""

    def analyze(
        self,
        context: Any,
        argv: "CustomRecognition.AnalyzeArg",
    ) -> Tuple[bool, Tuple[int, int, int, int]]:
        """识别回调：输出当帧导航状态与命令序列。"""
        params = NavigationParams.from_dict(argv.custom_recognition_param)
        node_name = getattr(argv, "node_name", None) or "PathFindingReco"
        session = controller.get_or_create(node_name, params)

        roi = argv.roi if argv.roi else None
        image = argv.image
        try:
            detail = session.perceive(context, image)
        except Exception:
            import traceback

            from utils.logger import logger

            logger.warning(
                "[PathFindingReco] perceive failed at %s:\n%s",
                node_name,
                traceback.format_exc(),
            )
            return False, (0, 0, 0, 0)

        box = (0, 0, 1280, 720)
        if session.movement.target is not None:
            x, y, w, h = session.movement.target.bbox
            box = (int(x), int(y), int(w), int(h))
        return bool(detail.get("hit")), box
