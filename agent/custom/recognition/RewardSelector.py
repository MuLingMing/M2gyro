# -*- coding: utf-8 -*-
"""
密函报酬选择识别器

功能说明：
1. 识别三个位置的奖励图标类型（仅武器：图纸和零件）
2. 识别武器零件的持有数
3. 根据优先级逻辑返回选择结果和点击位置

奖励分类与优先级：
- 武器图纸 → 选最左侧
- 武器零件（≥2个时选持有数少的，否则选该位置）
- 角色碎片/魔之楔/无匹配 → 默认选最左侧

返回值：
- box: 点击区域 [x, y, w, h]
- detail: {"index": 0/1/2, "category": str, "decision_path": str, "rewards": [...], "reward_details": [...]}
"""

from maa.context import Context
from maa.custom_recognition import CustomRecognition
from maa.define import OCRResult, BoxAndScoreResult
from maa.pipeline import JRecognitionType, JOCR, JTemplateMatch
from utils.logger import logger
import re
import time
from typing import List, Dict, Any, Tuple
import numpy

TEMPLATE_WEAPON_BLUEPRINT = "委托密函/武器图纸"
TEMPLATE_WEAPON_PART = "委托密函/武器零件"

TITLE_TEXT = "密函报酬选择"
TITLE_ROI = [560, 140, 160, 100]

CLICK_ABSOLUTE_ROIS = [
    [415, 450, 100, 60],
    [590, 450, 100, 60],
    [765, 450, 100, 60],
]

MERGED_ICON_ROI = [420, 340, 440, 100]

CARD_X_THRESHOLDS = [553, 728]

TEMPLATE_THRESHOLD = 0.85


class RewardSelector(CustomRecognition):
    """
    密函报酬选择识别器

    注册方式：通过 agent/custom.json 动态注册，不引入装饰器
    """

    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        """
        执行奖励识别逻辑

        执行流程:
        1. 验证输入图像
        2. 检查任务是否停止
        3. 检查标题文字"密函报酬选择"是否存在
        4. 识别武器图标（图纸优先，零件多匹配）
        5. 根据优先级逻辑确定选择位置
        6. 返回选择位置的点击区域
        """
        image = argv.image

        if image is None or not isinstance(image, numpy.ndarray) or image.size == 0:
            logger.error("RewardSelector: 输入图像无效")
            return CustomRecognition.AnalyzeResult(
                box=None, detail={"hit": False, "reason": "invalid_image"}
            )

        if context.tasker.stopping:
            return CustomRecognition.AnalyzeResult(
                box=None, detail={"hit": False, "reason": "stopping"}
            )

        if not self._check_title(context, image):
            return CustomRecognition.AnalyzeResult(box=None, detail={"hit": False})

        if context.tasker.stopping:
            return CustomRecognition.AnalyzeResult(
                box=None, detail={"hit": False, "reason": "stopping"}
            )

        start_time = time.monotonic()
        selection = self._recognize_and_select(context, image)
        elapsed = time.monotonic() - start_time

        logger.info(
            f"RewardSelector: 选择={selection['index']} "
            f"分类={selection['category']} "
            f"决策路径={selection['decision_path']} "
            f"耗时={elapsed:.3f}s"
        )

        return CustomRecognition.AnalyzeResult(
            box=CLICK_ABSOLUTE_ROIS[selection["index"]],
            detail=selection,
        )

    def _check_title(self, context: Context, image: numpy.ndarray) -> bool:
        """检查标题文字是否存在"""
        try:
            reco_param = JOCR(
                expected=[TITLE_TEXT],
                roi=(TITLE_ROI[0], TITLE_ROI[1], TITLE_ROI[2], TITLE_ROI[3]),
            )
            result = context.run_recognition_direct(
                JRecognitionType.OCR,
                reco_param,
                image,
            )
            if (
                result
                and result.hit
                and result.best_result
                and isinstance(result.best_result, OCRResult)
            ):
                text = result.best_result.text
                if text and TITLE_TEXT in text:
                    return True
        except Exception as e:
            logger.error(
                f"RewardSelector: _check_title 异常 "
                f"image_shape={image.shape if image is not None else None}, error={e}",
                exc_info=True,
            )
        return False

    def _recognize_and_select(
        self, context: Context, image: numpy.ndarray
    ) -> Dict[str, Any]:
        """
        识别武器图标并确定选择位置

        流程：
        1. 先匹配图纸（单独匹配，命中则返回）
        2. 再匹配零件（使用all_results筛选）
        3. 按需识别持有数（仅≥2零件时）
        4. 返回选择结果
        """
        blueprint_card = self._match_blueprint(context, MERGED_ICON_ROI, image)
        if blueprint_card == 0:
            logger.debug("RewardSelector: 图纸在第一位，直接选择")
            return self._build_result(
                index=0,
                category="weapon",
                decision_path="blueprint_first",
                blueprint_card=0,
            )

        if context.tasker.stopping:
            return self._build_result(
                index=0, category="unknown", decision_path="stopping"
            )

        part_cards = self._match_all_parts(context, MERGED_ICON_ROI, image)
        logger.debug(f"RewardSelector: 零件位置={part_cards}")

        if len(part_cards) == 0:
            logger.debug("RewardSelector: 无零件，兜底选最左")
            return self._build_result(
                index=0,
                category="unknown",
                decision_path="no_weapon_match",
            )

        if len(part_cards) == 1:
            logger.debug(f"RewardSelector: 单个零件位置={part_cards[0]}")
            return self._build_result(
                index=part_cards[0][0],
                category="weapon_part",
                decision_path="single_part",
                part_cards=part_cards,
            )

        if context.tasker.stopping:
            return self._build_result(
                index=0, category="unknown", decision_path="stopping"
            )

        logger.debug("RewardSelector: 多个零件，识别持有数")
        counts = self._recognize_counts_merged(context, image, part_cards)
        logger.debug(f"RewardSelector: 持有数={counts}")

        min_count = min(counts.values())
        for card_idx, count in counts.items():
            if count == min_count:
                logger.debug(
                    f"RewardSelector: 持有数最少的位置={card_idx}, 持有数={min_count}"
                )
                return self._build_result(
                    index=card_idx,
                    category="weapon_part",
                    decision_path="min_count",
                    part_cards=part_cards,
                    counts=counts,
                )

        return self._build_result(index=0, category="unknown", decision_path="fallback")

    def _match_blueprint(
        self, context: Context, roi: List[int], image: numpy.ndarray
    ) -> int:
        """匹配武器图纸，返回图纸所在卡牌索引（0/1/2），未命中返回 -1"""
        if context.tasker.stopping:
            return -1

        try:
            reco_param = JTemplateMatch(
                template=[TEMPLATE_WEAPON_BLUEPRINT],
                roi=(roi[0], roi[1], roi[2], roi[3]),
                threshold=[TEMPLATE_THRESHOLD],
            )
            result = context.run_recognition_direct(
                JRecognitionType.TemplateMatch,
                reco_param,
                image,
            )
            if (
                result
                and result.hit
                and result.best_result
                and isinstance(result.best_result, BoxAndScoreResult)
            ):
                box_x = self._extract_box_x(result.best_result.box)
                card_idx = self._infer_card_index(box_x)
                logger.debug(f"RewardSelector: 图纸匹配成功 位置={card_idx} x={box_x}")
                return card_idx
        except Exception as e:
            logger.error(
                f"RewardSelector: _match_blueprint 异常 roi={roi}, error={e}",
                exc_info=True,
            )
        logger.debug("RewardSelector: 图纸未匹配")
        return -1

    def _match_all_parts(
        self, context: Context, roi: List[int], image: numpy.ndarray
    ) -> List[Tuple[int, float]]:
        """匹配所有武器零件（使用all_results筛选threshold以上的），返回 [(card_index, score), ...]"""
        if context.tasker.stopping:
            return []

        matches = []
        try:
            reco_param = JTemplateMatch(
                template=[TEMPLATE_WEAPON_PART],
                roi=(roi[0], roi[1], roi[2], roi[3]),
                threshold=[TEMPLATE_THRESHOLD],
            )
            result = context.run_recognition_direct(
                JRecognitionType.TemplateMatch,
                reco_param,
                image,
            )
            if result and result.hit and result.all_results:
                for r in result.all_results:
                    if (
                        isinstance(r, BoxAndScoreResult)
                        and r.score >= TEMPLATE_THRESHOLD
                    ):
                        box_x = self._extract_box_x(r.box)
                        card_idx = self._infer_card_index(box_x)
                        matches.append((card_idx, r.score))
                        logger.debug(
                            f"RewardSelector: 零件匹配 位置={card_idx} 分数={r.score:.2f}"
                        )
        except Exception as e:
            logger.error(
                f"RewardSelector: _match_all_parts 异常 roi={roi}, error={e}",
                exc_info=True,
            )

        return matches

    def _recognize_counts_merged(
        self,
        context: Context,
        image: numpy.ndarray,
        part_cards: List[Tuple[int, float]],
    ) -> Dict[int, int]:
        """合并OCR识别多个零件的持有数，返回 {card_index: count}"""
        if context.tasker.stopping:
            return {}

        merged_count_roi = [415, 450, 450, 60]
        part_indices = {pc[0] for pc in part_cards}
        counts = {}

        try:
            reco_param = JOCR(
                roi=(
                    merged_count_roi[0],
                    merged_count_roi[1],
                    merged_count_roi[2],
                    merged_count_roi[3],
                ),
                replace=[["持有数", ""]],
            )
            result = context.run_recognition_direct(
                JRecognitionType.OCR, reco_param, image
            )
            if result and result.hit and result.all_results:
                for r in result.all_results:
                    if isinstance(r, OCRResult) and r.text and r.box:
                        numbers = re.findall(r"\d+", r.text.strip())
                        if numbers:
                            box_x = self._extract_box_x(r.box)
                            card_idx = self._infer_card_index(box_x)
                            if card_idx in part_indices:
                                counts[card_idx] = int(numbers[0])
                                logger.debug(
                                    f"RewardSelector: 持有数 位置={card_idx} 数量={counts[card_idx]}"
                                )
        except Exception as e:
            logger.error(
                f"RewardSelector: _recognize_counts_merged 异常 error={e}",
                exc_info=True,
            )

        for card_idx, _ in part_cards:
            if card_idx not in counts:
                counts[card_idx] = 0

        return counts

    def _extract_box_x(self, box) -> int:
        """从 box 对象或列表中提取 x 坐标"""
        if isinstance(box, (list, tuple)):
            return box[0]
        return box.x

    def _infer_card_index(self, x: int) -> int:
        """根据x坐标推断卡牌索引"""
        if x < CARD_X_THRESHOLDS[0]:
            return 0
        elif x < CARD_X_THRESHOLDS[1]:
            return 1
        else:
            return 2

    def _build_result(
        self,
        index: int,
        category: str,
        decision_path: str,
        blueprint_card: int = -1,
        part_cards: List[Tuple[int, float]] = [],
        counts: Dict[int, int] = {},
    ) -> Dict[str, Any]:
        """构建返回结果"""
        if part_cards is None:
            part_cards = []
        if counts is None:
            counts = {}

        rewards = ["", "", ""]
        reward_details = [
            {"position": 0, "icon": "", "count": 0},
            {"position": 1, "icon": "", "count": 0},
            {"position": 2, "icon": "", "count": 0},
        ]

        if blueprint_card >= 0:
            rewards[blueprint_card] = TEMPLATE_WEAPON_BLUEPRINT
            reward_details[blueprint_card]["icon"] = TEMPLATE_WEAPON_BLUEPRINT

        for card_idx, score in part_cards:
            rewards[card_idx] = TEMPLATE_WEAPON_PART
            reward_details[card_idx]["icon"] = TEMPLATE_WEAPON_PART
            if card_idx in counts:
                reward_details[card_idx]["count"] = counts[card_idx]

        return {
            "index": index,
            "category": category,
            "decision_path": decision_path,
            "rewards": rewards,
            "reward_details": reward_details,
        }
