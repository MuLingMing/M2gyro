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
5. 计算目标相对于屏幕中心的方向（forward/backward/left/right/centered）
6. 评估目标运动状态（approaching/arrived/stuck）
7. 兼容 IfElseAction 分支（返回 hit_node="if"/"else"）

识别流程（职责分离）：
1. _parse_param: 解析参数并计算优先级顺序
2. _collect_targets: 收集所有匹配目标
   - priority 模式短路识别（命中即停）
   - nearest/composite 模式全量识别 + 距离提取
3. _select_target: 使用 selector/ 目录下的选择器类从候选列表中选择最优目标
   - PriorityTargetSelector
   - NearestTargetSelector
   - CompositeTargetSelector
4. _calculate_direction: 计算移动方向（forward/backward/left/right/centered）
5. _evaluate_movement_state: 评估运动状态（approaching/arrived/stuck）

返回值：CustomRecognition.AnalyzeResult
- hit=True,  hit_node="if"  → 识别到目标
- hit=False, hit_node="else" → 未识别到目标
- direction="centered" 表示目标已在屏幕中心死区内，无需移动
- state="approaching"/"arrived"/"stuck" 表示目标运动状态
"""

import json
import logging
import math
import re
from typing import Any, ClassVar, Dict, List, Optional, Tuple, Union

import numpy as np
from maa.context import Context
from maa.custom_recognition import CustomRecognition
from maa.define import OCRResult, RectType, TemplateMatchResult
from maa.pipeline import JOCR, JRecognitionType, JTemplateMatch

from ..selector import (
    CompositeTargetSelector,
    NearestTargetSelector,
    PriorityTargetSelector,
    TargetInfo,
    TargetSelector,
)
from .param import PathFindingParam

logger = logging.getLogger(__name__)

# 屏幕中心坐标（720p 基准）
SCREEN_CENTER = (640, 360)
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720


class PathFindingReco(CustomRecognition):
    # 跨帧状态存储，按节点名隔离。生命周期跟随 Python 进程。
    _path_state: ClassVar[dict[str, dict]] = {}
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
        "dead_zone": 50,                          // 方向判断死区/像素（可选，默认 50）
        "arrival_distance": 30,                   // 到达判定距离阈值/像素（可选，默认 30）
        "stuck_threshold": 3,                     // 卡住判定连续帧数（可选，默认 3）
        "stuck_distance_tolerance": 5,            // 卡住距离容差/像素（可选，默认 5）
        "stuck_center_tolerance": 10              // 卡住中心偏移容差/像素（可选，默认 10）
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
    - arrival_distance: 距离 ≤ 此值时判定为已到达
    - stuck_threshold: 连续多少帧距离/中心几乎无变化才判定为卡住
    - stuck_distance_tolerance: 相邻两帧距离变化 < 此值视为无进展
    - stuck_center_tolerance: 相邻两帧目标中心偏移 < 此值视为无进展

    返回值格式（兼容 IfElseAction）：
    - hit=True, hit_node="if": 识别到目标，detail 包含 target/direction/state
    - hit=False, hit_node="else": 未识别到目标
    - direction="centered": 目标在屏幕中心死区内，无需移动
    - state="approaching"/"arrived"/"stuck": 目标运动状态

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
    ) -> CustomRecognition.AnalyzeResult | RectType | None:
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
        direction = self._calculate_direction(selected.center, param.dead_zone)

        # 6. 计算运动状态（到达 / 卡住 / 接近中）
        node_name = getattr(argv, "node_name", "PathFindingReco")
        state = self._evaluate_movement_state(node_name, selected, param)

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
                "state": state,
            },
        )

    def _parse_param(self, raw_param: Union[str, Dict[str, Any], None]) -> PathFindingParam:
        """
        解析参数

        参数:
        - raw_param: 原始参数，可能为 str（JSON）或 dict

        返回值:
        - PathFindingParam: 解析后的参数对象
        """
        if isinstance(raw_param, str):
            try:
                param = json.loads(raw_param)
            except json.JSONDecodeError:
                logger.warning("Failed to decode custom_recognition_param as JSON")
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

        return PathFindingParam(
            ordered_templates=ordered_templates,
            roi=tuple(param.get("roi", [0, 0, SCREEN_WIDTH, SCREEN_HEIGHT])),
            threshold=param.get("threshold", 0.8),
            selector_type=param.get("selector_type", "priority"),
            distance_pattern=param.get("distance_pattern", r"(\d+)米"),
            distance_offset=param.get("distance_offset", [10, 10, 20, 20]),
            distance_threshold=param.get("distance_threshold", 0.3),
            dead_zone=param.get("dead_zone", 50),
            arrival_distance=param.get("arrival_distance", 30),
            stuck_threshold=param.get("stuck_threshold", 3),
            stuck_distance_tolerance=param.get("stuck_distance_tolerance", 5),
            stuck_center_tolerance=param.get("stuck_center_tolerance", 10),
        )

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
            return self._priority_order_by_index(
                expected_templates, selector_priority
            )
        return self._priority_order_by_name(expected_templates, selector_priority)

    def _priority_order_by_index(
        self,
        expected_templates: List[str],
        selector_priority: List[Any],
    ) -> List[str]:
        """按索引格式计算优先级顺序。"""
        ordered: List[str] = []
        remaining = list(range(len(expected_templates)))

        for idx in selector_priority:
            if isinstance(idx, int) and 0 <= idx < len(expected_templates):
                ordered.append(expected_templates[idx])
                if idx in remaining:
                    remaining.remove(idx)
            else:
                logger.warning(
                    "Invalid selector_priority index %r for %d expected_templates",
                    idx,
                    len(expected_templates),
                )

        # 追加剩余的模板（按原顺序）
        for idx in remaining:
            ordered.append(expected_templates[idx])

        return ordered

    def _priority_order_by_name(
        self,
        expected_templates: List[str],
        selector_priority: List[Any],
    ) -> List[str]:
        """按名称格式计算优先级顺序。"""
        ordered: List[str] = []
        remaining = expected_templates.copy()

        for name in selector_priority:
            if isinstance(name, str) and name in remaining:
                ordered.append(name)
                remaining.remove(name)
            else:
                logger.warning(
                    "Invalid selector_priority name %r, available: %r",
                    name,
                    expected_templates,
                )

        # 追加剩余的模板（按原顺序）
        ordered.extend(remaining)

        return ordered

    def _collect_targets(
        self,
        context: Context,
        img: np.ndarray,
        param: PathFindingParam,
    ) -> List[TargetInfo]:
        """
        收集所有匹配的目标

        priority 模式短路识别（命中即停）；
        nearest/composite 模式全量识别并提取距离。

        参数:
        - context: MaaFramework 上下文
        - img: 输入图片
        - param: 识别参数

        返回值:
        - List[TargetInfo]: 收集到的目标列表（含距离信息）
        """
        targets: List[TargetInfo] = []
        for template_name in param.ordered_templates:
            target = self._match_template(
                context, img, template_name, param.roi, param.threshold
            )
            if target is not None:
                # 统一提取距离（保证 selector 输入一致）
                target = self._extract_distance(context, img, target, param)
                targets.append(target)

                # priority 模式短路：找到第一个命中即停止
                if param.selector_type == "priority":
                    break

        return targets

    def _select_target(
        self,
        targets: List[TargetInfo],
        param: PathFindingParam,
    ) -> Optional[TargetInfo]:
        """
        从候选目标列表中选择最优目标

        使用 selector/ 目录下的选择器类实现选择逻辑。

        参数:
        - targets: 候选目标列表
        - param: 识别参数

        返回值:
        - Optional[TargetInfo]: 选中的目标，没有则返回 None
        """
        if not targets:
            return None

        selector = self._create_selector(param)
        return selector.select(targets)

    def _create_selector(self, param: PathFindingParam) -> TargetSelector:
        """
        创建对应的 selector 实例（工厂方法）

        参数:
        - param: 识别参数

        返回值:
        - TargetSelector: 对应类型的选择器实例
        """
        selector_type = param.selector_type

        if selector_type == "priority":
            return PriorityTargetSelector(priority=param.ordered_templates)
        elif selector_type == "nearest":
            return NearestTargetSelector(fallback_to_first=True)
        elif selector_type == "composite":
            return CompositeTargetSelector(type_priority=param.ordered_templates)
        else:
            logger.warning(
                "Unknown selector_type %r, falling back to priority", selector_type
            )
            return PriorityTargetSelector(priority=param.ordered_templates)

    def _match_template(
        self,
        context: Context,
        img: np.ndarray,
        template_name: str,
        roi: tuple[int, int, int, int],
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
            green_mask=True,
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
        param: PathFindingParam,
    ) -> TargetInfo:
        """
        提取目标下方的距离信息

        参数:
        - context: MaaFramework 上下文
        - img: 输入图片
        - target: 目标信息
        - param: 识别参数

        返回值:
        - TargetInfo: 更新后的目标信息
        """
        # 计算 OCR 识别区域（基于 box 扩展 offset）
        x, y, w, h = target.bbox
        left, top, right, bottom = param.distance_offset
        roi = (
            max(0, x - left),
            max(0, y - top),
            w + left + right,
            h + top + bottom,
        )

        try:
            reco_param = JOCR(
                expected=[param.distance_pattern],
                roi=roi,
                threshold=param.distance_threshold,
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
                        match = re.search(param.distance_pattern, text)
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
        except Exception as e:
            logger.warning(
                "Distance extraction failed for %s (roi=%s): %s",
                target.template,
                roi,
                e,
                exc_info=True,
            )

        return target

    def _evaluate_movement_state(
        self,
        node_name: str,
        selected: TargetInfo,
        param: PathFindingParam,
    ) -> str:
        """
        评估目标运动状态

        通过类级状态按节点名跨帧跟踪目标距离和中心位置，判定：
        - arrived: 距离 ≤ arrival_distance
        - stuck: 连续 stuck_threshold 帧距离/中心几乎无变化
        - approaching: 其他情况

        参数:
        - node_name: 当前 Pipeline 节点名，用于隔离不同节点的状态
        - selected: 当前选中的目标
        - param: 识别参数

        返回值:
        - str: "approaching" / "arrived" / "stuck"
        """
        distance = selected.distance
        if distance is not None and distance <= param.arrival_distance:
            self._path_state.pop(node_name, None)
            return "arrived"

        prev_state = self._path_state.get(node_name, {})
        last_distance = prev_state.get("last_distance")
        last_center = prev_state.get("last_center")
        stuck_count = prev_state.get("stuck_count", 0)

        current_center = selected.center
        current_distance = selected.distance

        if self._is_stuck(
            current_center,
            last_center,
            current_distance,
            last_distance,
            param,
        ):
            stuck_count += 1
        else:
            stuck_count = 0

        self._path_state[node_name] = {
            "last_distance": current_distance,
            "last_center": current_center,
            "stuck_count": stuck_count,
        }

        if stuck_count >= param.stuck_threshold:
            return "stuck"
        return "approaching"

    def _is_stuck(
        self,
        current_center: Tuple[float, float],
        last_center: Any,
        current_distance: int | None,
        last_distance: Any,
        param: PathFindingParam,
    ) -> bool:
        """
        判断相邻两帧是否无进展

        优先使用距离信息：当距离未明显缩短（变化 ≤ stuck_distance_tolerance）时视为卡住。
        无距离信息时回退到目标中心偏移判断。

        参数:
        - current_center: 当前目标中心
        - last_center: 上一帧目标中心
        - current_distance: 当前距离
        - last_distance: 上一帧距离
        - param: 识别参数

        返回值:
        - bool: 是否卡住
        """
        if isinstance(current_distance, int) and isinstance(last_distance, int):
            # 距离未缩短超过容差视为无进展（负值表示距离增加，也视为卡住）
            return (last_distance - current_distance) <= param.stuck_distance_tolerance

        if isinstance(last_center, (list, tuple)) and len(last_center) == 2:
            dx = current_center[0] - last_center[0]
            dy = current_center[1] - last_center[1]
            return math.hypot(dx, dy) <= param.stuck_center_tolerance

        # 首帧无历史数据，不判定为卡住
        return False

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
        - str: 方向（forward/backward/left/right/centered）

        角度分箱规则（使用 atan2(-dy, dx) 将屏幕坐标转换为游戏方向）：
        -   -45° ≤ angle <   45° → right   （目标在右）
        -    45° ≤ angle <  135° → forward （目标在上）
        -   135° ≤ angle <  180° 或 -180° ≤ angle < -135° → left  （目标在左）
        -  -135° ≤ angle <  -45° → backward（目标在下）
        - 目标在死区内 → centered
        """
        tx, ty = target_center
        cx, cy = SCREEN_CENTER

        dx = tx - cx
        dy = ty - cy

        # 1. 圆形死区：欧氏距离（比矩形死区更自然）
        if math.hypot(dx, dy) <= dead_zone:
            return "centered"

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
