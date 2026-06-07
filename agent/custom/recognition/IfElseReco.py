# -*- coding: utf-8 -*-
"""
条件分支识别器

功能说明：
1. 按优先级依次识别两个节点（A、B）
2. 节点A识别成功 → 返回 box=A.box, hit=True
3. 节点A未识别到，节点B识别成功 → 返回 box=B.box, hit=False
4. A、B均未识别到 → 返回 box=None，节点未命中
5. 识别成功但 box=None 时，将 box 设为 [0,0,0,0]

与 IfElse 动作器配合使用：
- hit=True  → IfElse 执行 true 分支
- hit=False → IfElse 执行 false 分支
- box=None  → 节点未命中，Pipeline 重试/走 exceeded_next
"""

import json
from typing import Any, Dict, Optional, Tuple, Union

import numpy
from maa.context import Context
from maa.custom_recognition import CustomRecognition
from maa.define import RectType
from utils.logger import logger


class IfElseReco(CustomRecognition):
    """
    条件分支识别器

    注册方式：通过 agent/custom.json 动态注册

    参数格式（custom_recognition_param）：
    {
        "if_node": "NodeA",
        "else_node": "NodeB"
    }

    字段说明：
    - if_node: 优先识别的节点名，识别成功返回 hit=True
    - else_node: 次优先识别的节点名，识别成功返回 hit=False

    返回值逻辑：
    1. if_node 识别成功 → AnalyzeResult(box=if_node.box, detail={hit=True})
    2. if_node 未命中，else_node 识别成功 → AnalyzeResult(box=else_node.box, detail={hit=False})
    3. 两者均未命中 → AnalyzeResult(box=None, detail={hit=False})
    4. 识别成功但 box=None 时 → box 设为 [0,0,0,0]

    Pipeline 使用示例：
    {
        "ConditionCheck": {
            "recognition": "IfElseReco",
            "custom_recognition_param": {
                "if_node": "TargetA",
                "else_node": "TargetB"
            },
            "action": "Custom",
            "custom_action": "IfElse",
            "custom_action_param": {
                "true": [{"action": "Click", "param": {"target": true}}],
                "false": ["HandleFalse"]
            }
        }
    }
    """

    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> Union[CustomRecognition.AnalyzeResult, Optional[RectType]]:
        """
        执行条件分支识别主流程

        参数:
        - context: MaaFramework 上下文对象
        - argv: 识别参数，包含输入图像和 custom_recognition_param

        返回值:
        - CustomRecognition.AnalyzeResult:
            if_node 命中: box=if_node.box, detail={hit=True}
            else_node 命中: box=else_node.box, detail={hit=False}
            均未命中: box=None, detail={hit=False}
        """
        image = argv.image

        if image is None or not isinstance(image, numpy.ndarray) or image.size == 0:
            logger.error("IfElseReco: 输入图像无效")
            return CustomRecognition.AnalyzeResult(
                box=None, detail={"hit": False, "reason": "invalid_image"}
            )

        if context.tasker.stopping:
            return CustomRecognition.AnalyzeResult(
                box=None, detail={"hit": False, "reason": "stopping"}
            )

        params = self._parse_params(argv.custom_recognition_param)
        if_node = params.get("if_node")
        else_node = params.get("else_node")

        if not if_node and not else_node:
            logger.error("IfElseReco: if_node 和 else_node 均未指定")
            return CustomRecognition.AnalyzeResult(
                box=None, detail={"hit": False, "reason": "no_nodes_specified"}
            )

        # 识别 if_node
        if if_node:
            result_a = context.run_recognition(if_node, image)
            if result_a and result_a.hit:
                box = self._normalize_box(result_a.box)
                return CustomRecognition.AnalyzeResult(
                    box=box,
                    detail={"hit": True, "matched_node": if_node}
                )

        # 识别 else_node
        if else_node:
            result_b = context.run_recognition(else_node, image)
            if result_b and result_b.hit:
                box = self._normalize_box(result_b.box)
                return CustomRecognition.AnalyzeResult(
                    box=box,
                    detail={"hit": False, "matched_node": else_node}
                )

        # 均未命中
        return CustomRecognition.AnalyzeResult(
            box=None,
            detail={"hit": False, "reason": "no_match"}
        )

    @staticmethod
    def _parse_params(raw_param: str | dict | None) -> Dict[str, Any]:
        """
        解析 custom_recognition_param 参数

        参数:
        - raw_param: 原始参数，可能为 str（JSON）或 dict

        返回值:
        - dict: 包含 "if_node" 和 "else_node" 的字典
        """
        if isinstance(raw_param, str):
            try:
                return json.loads(raw_param)
            except json.JSONDecodeError as e:
                logger.error(f"IfElseReco: 参数解析失败: {e}")
                return {}
        elif isinstance(raw_param, dict):
            return raw_param
        return {}

    @staticmethod
    def _normalize_box(box: Optional[RectType]) -> RectType:
        """
        标准化 box，None 转换为 [0,0,0,0]

        参数:
        - box: 原始 box 值

        返回值:
        - RectType: 标准化后的 box
        """
        if box is None:
            return [0, 0, 0, 0]
        return box
