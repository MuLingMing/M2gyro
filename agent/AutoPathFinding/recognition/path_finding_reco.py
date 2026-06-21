# -*- coding: utf-8 -*-
"""
自动寻路识别器

使用 MaaFramework 内置 TemplateMatch 识别目标图标，支持多目标识别、
距离提取和方向计算。

功能说明：
1. 使用 MaaFramework 内置 TemplateMatch 识别目标图标
2. 支持三种选择器模式：priority（优先级）、nearest（就近）、composite（组合）
3. 支持索引和名称两种 selector_priority 格式
4. 提取目标图标下方的距离信息（OCR，可配置正则和偏移）
5. 计算目标相对于屏幕中心的方向（forward/backward/left/right）
6. 兼容 IfElseAction 分支（返回 hit_node="if"/"else"）

识别流程（职责分离）：
1. _parse_param: 解析参数 + _calculate_priority_order 计算优先级顺序
2. _collect_targets: 收集所有匹配目标
   - priority 模式短路识别（命中即停）
   - nearest/composite 模式全量识别 + 距离提取
3. _select_target: 使用 selector/ 目录下的选择器类从候选列表中选择最优目标
   - PriorityTargetSelector
   - NearestTargetSelector
   - CompositeTargetSelector
4. _calculate_direction: 计算移动方向（forward/backward/left/right）

返回值：CustomRecognition.AnalyzeResult
- hit=True,  hit_node="if"  → 识别到目标
- hit=False, hit_node="else" → 未识别到目标
"""

import json
import math
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from maa.context import Context
from maa.custom_recognition import CustomRecognition
from maa.define import RectType, TemplateMatchResult, OCRResult
from maa.pipeline import JOCR, JRecognitionType, JTemplateMatch

from ..selector import (
    CompositeTargetSelector,
    NearestTargetSelector,
    PriorityTargetSelector,
    TargetInfo,
    TargetSelector,
)

# 屏幕中心坐标（720p 基准）
SCREEN_CENTER = (640, 360)
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720


class PathFindingReco(CustomRecognition):
    """
    自动寻路识别器

    参数格式（JSON）：
    {
        "expected_templates": ["quest_icon.png", "npc_icon.png"],  // 期望匹配的模板列表（必填）
        "roi": [0, 0, 1280, 720],                 // 识别区域 [x, y, w, h]（可选，默认全屏）
        "threshold": 0.8,                         // 匹配阈值 0-1（可选，默认 0.8）
        "selector_type": "priority",              // 选择器类型（可选，默认 "priority"）
        "selector_priority": [0, 1],              // 选择器优先级（可选，支持索引或名称格式）
        "distance_pattern": "(\\d+)米",           // 距离 OCR 正则表达式（可选）
        "distance_offset": [10, 10, 20, 20],      // 距离 OCR 区域偏移 [l, t, r, b]（可选）
        "distance_threshold": 0.3,                // OCR 置信度阈值（可选）
        "dead_zone": 50                           // 方向判断死区/像素（可选，默认 50）
    }

    字段说明：
    - expected_templates: 模板名称或路径列表，同时作为默认识别优先级
    - selector_type: "priority"（短路识别）、"nearest"（全量识别+距离排序）、"composite"（优先级+距离）
    - selector_priority:
    - 索引格式: [1, 2] 表示第2个模板 > 第3个模板 > 第1个模板
    - 名称格式: ["npc_icon.png"] 表示 npc > 其余模板按原顺序
    - 未设置时: 使用 expected_templates 原始顺序
    - distance_pattern: 正则表达式，必须包含一个捕获组用于提取数字
    - distance_offset: 相对于目标 box 的扩展像素 [left, top, right, bottom]

    返回值格式（兼容 IfElseAction）：
    - hit=True, hit_node="if": 识别到目标，detail 包含 target/direction
    - hit=False, hit_node="else": 未识别到目标

    Pipeline 使用示例：
    {
        "AutoPathFinding": {
            "recognition": "Custom",
            "custom_recognition": "PathFindingReco",
            "custom_recognition_param": {
                "expected_templates": ["副本/目标点", "副本/NPC"],
                "selector_type": "priority",
                "selector_priority": [1, 0]
            },
            "action": "Custom",
            "custom_action": "IfElseAction",
            "custom_action_param": {
                "if": ["PathFinderAction"],
                "else": ["TaskComplete"]
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
        执行寻路识别

        参数:
        - context: MaaFramework 上下文对象
        - argv: 识别参数，包含 image、roi、custom_recognition_param 等

        返回值:
        - CustomRecognition.AnalyzeResult: 识别结果
        - Optional[RectType]: 识别到的位置
        - None: 识别失败
        """
        # 1. 解析参数
        param = self._parse_param(argv.custom_recognition_param)

        # 2. 获取图片
        img = argv.image
        if img is None or img.size == 0:
            return None

        # 3. 收集目标（按 selector_type 决定是否短路）
        targets = self._collect_targets(context, img, param)
        if not targets:
            return CustomRecognition.AnalyzeResult(
                box=None, detail={"hit": False, "hit_node": "else"}
            )

        # 4. 选择最优目标（使用 selector/ 下的选择器类）
        selected = self._select_target(targets, param)
        if not selected:
            return CustomRecognition.AnalyzeResult(
                box=None, detail={"hit": False, "hit_node": "else"}
            )

        # 5. 计算移动方向
        direction = self._calculate_direction(selected.center, param["dead_zone"])

        return CustomRecognition.AnalyzeResult(
            box=list(selected.bbox),
            detail={
                "hit": True,
                "hit_node": "if",
                "target": {
                    "template": selected.template,
                    "center": list(selected.center),
                    "bbox": list(selected.bbox),
                    "score": selected.score,
                    "distance": selected.distance,
                },
                "direction": direction,
            },
        )

    def _parse_param(self, raw_param: Union[str, Dict[str, Any], None]) -> dict:
        """
        解析参数

        参数:
        - raw_param: 原始参数，可能为 str（JSON）或 dict

        返回值:
        - dict: 解析后的参数字典
        """
        if isinstance(raw_param, str):
            try:
                param = json.loads(raw_param)
            except json.JSONDecodeError:
                param = {}
        elif isinstance(raw_param, dict):
            param = raw_param
        else:
            param = {}

        expected_templates = param.get("expected_templates", [])
        selector_priority = param.get("selector_priority", [])

        # 计算最终的优先级顺序
        ordered_templates = self._calculate_priority_order(
            expected_templates, selector_priority
        )

        return {
            "ordered_templates": ordered_templates,
            "roi": tuple(param.get("roi", [0, 0, SCREEN_WIDTH, SCREEN_HEIGHT])),
            "threshold": param.get("threshold", 0.8),
            "selector_type": param.get("selector_type", "priority"),
            "distance_pattern": param.get("distance_pattern", r"(\d+)米"),
            "distance_offset": param.get("distance_offset", [10, 10, 20, 20]),
            "distance_threshold": param.get("distance_threshold", 0.3),
            "dead_zone": param.get("dead_zone", 50),
        }

    def _calculate_priority_order(
        self,
        expected_templates: List[str],
        selector_priority: List[Any],
    ) -> List[str]:
        """
        计算最终的优先级顺序

        参数:
        - expected_templates: 原始模板列表
        - selector_priority: 用户指定的优先级（索引或名称）

        返回值:
        - List[str]: 按优先级排序后的模板列表
        """
        if not selector_priority:
            return expected_templates.copy()

        # 判断是索引格式还是名称格式
        if selector_priority and isinstance(selector_priority[0], int):
            # 索引格式
            ordered: List[str] = []
            remaining = list(range(len(expected_templates)))

            for idx in selector_priority:
                if isinstance(idx, int) and 0 <= idx < len(expected_templates):
                    ordered.append(expected_templates[idx])
                    if idx in remaining:
                        remaining.remove(idx)

            # 追加剩余的模板（按原顺序）
            for idx in remaining:
                ordered.append(expected_templates[idx])

            return ordered
        else:
            # 名称格式
            ordered: List[str] = []
            remaining = expected_templates.copy()

            for name in selector_priority:
                if isinstance(name, str) and name in remaining:
                    ordered.append(name)
                    remaining.remove(name)

            # 追加剩余的模板（按原顺序）
            ordered.extend(remaining)

            return ordered

    def _collect_targets(
        self,
        context: Context,
        img: np.ndarray,
        param: dict,
    ) -> List[TargetInfo]:
        """
        收集所有匹配的目标

        priority 模式短路识别（命中即停）；
        nearest/composite 模式全量识别并提取距离。

        参数:
        - context: MaaFramework 上下文
        - img: 输入图片
        - param: 参数字典

        返回值:
        - List[TargetInfo]: 收集到的目标列表（含距离信息）
        """
        roi = param.get("roi", (0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))
        threshold = param.get("threshold", 0.8)
        ordered_templates = param.get("ordered_templates", [])
        selector_type = param.get("selector_type", "priority")

        targets: List[TargetInfo] = []
        for template_name in ordered_templates:
            target = self._match_template(context, img, template_name, roi, threshold)
            if target is not None:
                # 统一提取距离（保证 selector 输入一致）
                target = self._extract_distance(context, img, target, param)
                targets.append(target)

                # priority 模式短路：找到第一个命中即停止
                if selector_type == "priority":
                    break

        return targets

    def _select_target(
        self,
        targets: List[TargetInfo],
        param: dict,
    ) -> Optional[TargetInfo]:
        """
        从候选目标列表中选择最优目标

        使用 selector/ 目录下的选择器类实现选择逻辑。

        参数:
        - targets: 候选目标列表
        - param: 参数字典

        返回值:
        - Optional[TargetInfo]: 选中的目标，没有则返回 None
        """
        if not targets:
            return None

        selector = self._create_selector(param)
        return selector.select(targets)

    def _create_selector(self, param: dict) -> TargetSelector:
        """
        创建对应的 selector 实例（工厂方法）

        参数:
        - param: 参数字典

        返回值:
        - TargetSelector: 对应类型的选择器实例
        """
        selector_type = param.get("selector_type", "priority")
        ordered_templates = param.get("ordered_templates", [])

        if selector_type == "priority":
            return PriorityTargetSelector(priority=ordered_templates)
        elif selector_type == "nearest":
            return NearestTargetSelector(fallback_to_first=True)
        elif selector_type == "composite":
            return CompositeTargetSelector(type_priority=ordered_templates)
        else:
            return PriorityTargetSelector(priority=ordered_templates)

    def _match_template(
        self,
        context: Context,
        img: np.ndarray,
        template_name: str,
        roi: Tuple[int, int, int, int],
        threshold: float,
    ) -> Optional[TargetInfo]:
        """
        单个模板匹配

        参数:
        - context: MaaFramework 上下文
        - img: 输入图片
        - template_name: 模板名称
        - roi: 识别区域
        - threshold: 匹配阈值

        返回值:
        - Optional[TargetInfo]: 匹配成功返回 TargetInfo，否则返回 None
        """
        reco_param = JTemplateMatch(
            template=[template_name],
            roi=roi,
            threshold=[threshold],
            green_mask=True
        )
        reco_detail = context.run_recognition_direct(
            JRecognitionType.TemplateMatch,
            reco_param,
            img,
        )

        if reco_detail is not None and reco_detail.hit:
            best_result = reco_detail.best_result
            if isinstance(best_result, TemplateMatchResult):
                box = best_result.box
                if box is not None:
                    # box 可能是 Rect 对象或 list [x, y, w, h]
                    if isinstance(box, (list, tuple)):
                        x, y, w, h = box[0], box[1], box[2], box[3]
                    else:
                        x, y, w, h = box.x, box.y, box.w, box.h
                    center = (x + w / 2, y + h / 2)
                    return TargetInfo(
                        template=template_name,
                        center=center,
                        bbox=(x, y, w, h),
                        score=best_result.score,
                    )

        return None

    def _extract_distance(
        self,
        context: Context,
        img: np.ndarray,
        target: TargetInfo,
        param: dict,
    ) -> TargetInfo:
        """
        提取目标下方的距离信息

        参数:
        - context: MaaFramework 上下文
        - img: 输入图片
        - target: 目标信息
        - param: 参数字典

        返回值:
        - TargetInfo: 更新后的目标信息
        """
        import re

        distance_pattern = param.get("distance_pattern", r"(\d+)米")
        distance_offset = param.get("distance_offset", [10, 10, 20, 20])
        distance_threshold = param.get("distance_threshold", 0.3)

        # 计算 OCR 识别区域（基于 box 扩展 offset）
        x, y, w, h = target.bbox
        left, top, right, bottom = distance_offset
        roi = (
            max(0, x - left),
            max(0, y - top),
            w + left + right,
            h + top + bottom,
        )

        try:
            reco_param = JOCR(
                expected=[distance_pattern],
                roi=roi,
                threshold=distance_threshold,
            )
            reco_detail = context.run_recognition_direct(
                JRecognitionType.OCR,
                reco_param,
                img,
            )

            if reco_detail is not None and reco_detail.hit:
                best_result = reco_detail.best_result
                if isinstance(best_result, OCRResult):
                    text = best_result.text
                    if text:
                        # 使用正则表达式提取数字
                        match = re.search(distance_pattern, text)
                        if match:
                            distance_str = match.group(1)
                            if distance_str.isdigit():
                                return TargetInfo(
                                    template=target.template,
                                    center=target.center,
                                    bbox=target.bbox,
                                    score=target.score,
                                    distance=int(distance_str),
                                )
        except Exception:
            pass

        return target

    def _calculate_direction(
        self,
        target_center: Tuple[float, float],
        dead_zone: int,
    ) -> str:
        """
        计算目标相对于屏幕中心的方向

        使用角度分箱（angular binning）+ 圆形死区，避免轴向 1-像素抖动。

        参数:
        - target_center: 目标中心坐标 (x, y)，允许浮点
        - dead_zone: 圆形死区半径（像素，欧氏距离）

        返回值:
        - str: 方向（forward/backward/left/right）

        角度分箱规则（使用 atan2(-dy, dx) 将屏幕坐标转换为游戏方向）：
        -   -45° ≤ angle <   45° → right   （目标在右）
        -    45° ≤ angle <  135° → forward （目标在上）
        -   135° ≤ angle <  180° 或 -180° ≤ angle < -135° → left  （目标在左）
        -  -135° ≤ angle <  -45° → backward（目标在下）
        """
        tx, ty = target_center
        cx, cy = SCREEN_CENTER

        dx = tx - cx
        dy = ty - cy

        # 1. 圆形死区：欧氏距离（比矩形死区更自然）
        if math.hypot(dx, dy) <= dead_zone:
            return "forward"

        # 2. 角度分箱：用 -dy 翻转以匹配游戏方向（屏幕上方 = forward）
        angle = math.degrees(math.atan2(-dy, dx))

        if -45 <= angle < 45:
            return "right"
        elif 45 <= angle < 135:
            return "forward"
        elif angle >= 135 or angle < -135:
            return "left"
        else:  # -135 <= angle < -45
            return "backward"
