# -*- coding: utf-8 -*-
"""
条件分支识别器

功能说明：
1. 按优先级依次识别节点：entry → if → elif → else
2. entry 识别成功 → 继续执行条件分支识别
3. if 识别成功 → 返回 box=if.box, hit=True, hit_node="if"
4. elif 识别成功 → 返回 box=elif.box, hit=True, hit_node="elif[index]"
5. else 识别成功 → 返回 box=else.box, hit=True, hit_node="else"
6. 均未识别到 → 返回 box=None, hit=False
7. 识别成功但 box=None 时，将 box 设为 [0,0,0,0]

与 IfElseAction 动作器配合使用：
- hit=True  → IfElseAction 根据 hit_node 执行对应分支
- box=None  → 节点未命中，Pipeline 重试/走 exceeded_next
"""

import json
from typing import Any, Dict, List, Optional, Union

import numpy
from maa.context import Context
from maa.custom_recognition import CustomRecognition
from maa.define import Rect, RectType
from utils.logger import logger


class IfElseReco(CustomRecognition):
    """
    条件分支识别器

    注册方式：通过 agent/custom.json 动态注册

    参数格式（custom_recognition_param）：
    {
        "entry": "Node_entry",
        "if": "NodeA",
        "elif": ["NodeB", "NodeC"],
        "else": "NodeD"
    }

    字段说明：
    - entry: 入口节点名（可选），识别成功则继续执行条件分支识别，否则返回 box=None, hit=False
    - if: 优先识别的节点名，识别成功返回 hit=True, detail.hit_node=if
    - elif: 次优先识别的节点名列表，识别成功返回 hit=True, detail.hit_node=elif[index]
    - else: 兜底分支（可选）
      - 省略: 不执行 else 分支，均未命中返回 hit=False
      - 字符串: 节点名，执行识别，识别成功返回 hit=True, hit_node="else"
      - true: 与 entry 共用识别结果，直接返回 box=entry.box, hit=True, hit_node="else"

    返回值逻辑：
    1. entry 未识别到 → AnalyzeResult(box=None, detail={hit=False})
    2. entry 识别成功 → 继续执行条件分支识别
    3. if 识别成功 → AnalyzeResult(box=if.box, detail={hit=True, hit_node="if"})
    4. if 未命中，elif 识别成功 → AnalyzeResult(box=elif.box, detail={hit=True, hit_node="elif[index]"})
    5. if 未命中，elif 未命中，else 识别成功 → AnalyzeResult(box=else.box, detail={hit=True, hit_node="else"})
    6. else=true → 跳过识别，直接返回 AnalyzeResult(box=entry.box, detail={hit=True, hit_node="else"})
    7. if、elif、else 均未识别到 → AnalyzeResult(box=None, detail={hit=False})
    8. 特殊情况：识别成功但 box=None 时 → box 设为 [0,0,0,0]
    9. 逻辑类似于 if-elif-else 语句

    Pipeline 使用示例：
    {
        "ConditionCheck": {
            "recognition": "IfElseReco",
            "custom_recognition_param": {
                "entry": "Node_entry",
                "if": "RecoA",
                "elif": ["RecoB", "RecoC"],
                "else": "RecoD"
            },
            "action": "Custom",
            "custom_action": "IfElseAction",
            "custom_action_param": {
                "if": [{"action": "Click", "param": {"target": true}}],
                "elif": ["ActionB", "ActionC"],
                "else": ["ActionD"]
            }
        }
    }

    Reco 和 Action 配合使用且一一对应：
    - detail.hit_node="if"       → IfElseAction 执行 if 分支
    - detail.hit_node="elif[0]"  → IfElseAction 执行 elif[0] 分支
    - detail.hit_node="elif[1]"  → IfElseAction 执行 elif[1] 分支
    - detail.hit_node="else"     → IfElseAction 执行 else 分支
    - box=None                   → 节点未命中
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
        - CustomRecognition.AnalyzeResult
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
        entry_node = params.get("entry")
        if_node = params.get("if")
        elif_nodes = params.get("elif", [])
        else_node = params.get("else")

        # 确保 elif 是列表
        if isinstance(elif_nodes, str):
            elif_nodes = [elif_nodes]

        # 检查是否有节点配置
        if not if_node and not elif_nodes and not else_node:
            logger.error("IfElseReco: 未配置任何识别节点")
            return CustomRecognition.AnalyzeResult(
                box=None, detail={"hit": False, "reason": "no_nodes_specified"}
            )

        # 识别 entry 节点（如果配置了）
        entry_box = None
        if entry_node:
            entry_result = context.run_recognition(entry_node, image)
            if not entry_result or not entry_result.hit:
                return CustomRecognition.AnalyzeResult(
                    box=None, detail={"hit": False, "hit_node": "entry_failed"}
                )
            entry_box = self._normalize_box(entry_result.box)

        # 识别 if 节点
        if if_node:
            result = context.run_recognition(if_node, image)
            if result and result.hit:
                box = self._normalize_box(result.box)
                return CustomRecognition.AnalyzeResult(
                    box=box,
                    detail={"hit": True, "hit_node": "if"}
                )

        # 依次识别 elif 节点列表
        for index, elif_node in enumerate(elif_nodes):
            if not elif_node:
                continue
            result = context.run_recognition(elif_node, image)
            if result and result.hit:
                box = self._normalize_box(result.box)
                return CustomRecognition.AnalyzeResult(
                    box=box,
                    detail={"hit": True, "hit_node": f"elif[{index}]"}
                )

        # 识别 else 节点
        if else_node is True:
            # else=true 兜底，直接视为识别成功，返回 entry 的识别框
            return CustomRecognition.AnalyzeResult(
                box=entry_box if entry_box is not None else Rect(0, 0, 0, 0),
                detail={"hit": True, "hit_node": "else"}
            )
        elif else_node:
            result = context.run_recognition(else_node, image)
            if result and result.hit:
                box = self._normalize_box(result.box)
                return CustomRecognition.AnalyzeResult(
                    box=box,
                    detail={"hit": True, "hit_node": "else"}
                )

        # 均未命中
        return CustomRecognition.AnalyzeResult(
            box=None,
            detail={"hit": False, "reason": "no_match"}
        )

    @staticmethod
    def _parse_params(raw_param: Union[str, Dict[str, Any], None]) -> Dict[str, Any]:
        """
        解析 custom_recognition_param 参数

        参数:
        - raw_param: 原始参数，可能为 str（JSON）或 dict

        返回值:
        - dict: 包含 entry, if, elif, else 的字典
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
        标准化 box，None 转换为 Rect(0,0,0,0)

        参数:
        - box: 原始 box 值

        返回值:
        - RectType: 标准化后的 box
        """
        if box is None:
            return Rect(0, 0, 0, 0)
        return box
