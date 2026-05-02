# -*- coding: utf-8 -*-
"""
密函报酬选择识别器

功能说明：
1. 识别三个奖励位置的档位标识（罗马数字Ⅰ/Ⅱ/Ⅲ）
2. 识别三个位置的奖励图标类型
3. 根据奖励分类和优先级逻辑返回选择结果和点击位置

奖励分类：
- 分类1（武器类）：Ⅰ档=武器图纸，Ⅱ/Ⅲ档=武器零件+其他
  - 优先级1：武器图纸（选最左侧）
  - 优先级2：只有1个零件时选该零件位置
  - 优先级3：≥2个零件时选持有数少的那个零件
  - 兜底：选最左侧
- 分类2（角色碎片类）：Ⅰ档=10碎片，Ⅱ档=2碎片+其他，Ⅲ档=其他
  - 默认选最左侧
- 分类3（魔之楔类）：Ⅰ档=魔之楔图纸，Ⅱ/Ⅲ档=其他
  - 默认选最左侧

根据奖励分类和优先级逻辑返回选择结果和点击位置。

优先级逻辑说明：
- 优先级1：第一档（Ⅰ）的奖励图标，武器图纸、魔之楔图纸、角色碎片
- 优先级2：零件奖励图标，武器零件
    - 优先级2.1：只有1个零件时选该零件位置
    - 优先级2.2：≥2个零件时选持有数少的那个零件
- 优先级3：选最左侧

根据奖励分类和优先级逻辑返回选择结果和点击位置。

返回值说明：

- box: 点击区域 [x, y, w, h]
"""

from maa.context import Context
from maa.custom_recognition import CustomRecognition
from maa.define import OCRResult
from maa.pipeline import JRecognitionType, JOCR, JTemplateMatch
from utils.logger import logger
import json
import re
from typing import List, Dict, Any
import numpy

# 奖励图标模板路径
# 根目录image
Weapon_blueprints = "委托密函/武器图纸"  # 武器图纸模板路径
Weapon_accessories = "委托密函/武器零件"  # 武器零件模板路径

# 标题识别（进入主体的前提条件）
TITLE_TEXT = "密函报酬选择"  # 标题文字
TITLE_ROI = [560, 140, 160, 100]  # 标题ROI区域（基于720p）

# 罗马数字识别
ROMAN_RANKS = ["Ⅰ", "Ⅱ", "Ⅲ"]

# 三个卡牌的ROI区域（基于720p）
CARD_ROIS = [
    [365, 185, 200, 400],  # 左
    [540, 185, 200, 400],  # 中
    [715, 185, 200, 400],  # 右
]

# 点击位置ROI（绝对坐标）
CLICK_ROIS = [
    [415, 450, 100, 60],  # 卡牌1 点击
    [590, 450, 100, 60],  # 卡牌2 点击
    [765, 450, 100, 60],  # 卡牌3 点击
]

# 各子区域ROI偏移（相对于卡牌）
RANK_ROI = [60, 60, -120, -320]  # 罗马数字区域
ICON_ROI = [55, 155, -110, -300]  # 图标区域
COUNT_ROI = [50, 265, -100, -340]  # 持有数区域


class RewardSelector(CustomRecognition):
    """
    密函报酬选择识别器


    字段说明：
    - 无

    返回值：
    - box: 点击区域 [x, y, w, h]
    """

    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        """
        执行奖励识别逻辑

        参数:
        - context: 上下文对象
        - argv: 分析参数，包含 node_name、custom_recognition_param、image 等

        返回值:
        - CustomRecognition.AnalyzeResult: 识别结果
        - box: 点击区域 [x, y, w, h]


        执行流程:
        1. 解析并验证参数
        2. 检查任务是否停止
        3. 检查标题文字"密函报酬选择"是否存在
        4. 使用 argv.image 识别三个位置的奖励
        5. 根据优先级逻辑确定选择位置
        6. 返回选择位置的点击区域
        """

        # 获取图像
        image = argv.image

        # 检查标题文字"密函报酬选择"是否存在（进入主体的前提条件）
        if not self._check_title(context, image):
            return CustomRecognition.AnalyzeResult(box=None, detail={"hit": False})

        # 识别三个位置的奖励
        rewards = self._recognize_rewards(context, image)

        # 计算选择位置
        selection = self._determine_selection(rewards)

        return CustomRecognition.AnalyzeResult(
            box=CLICK_ROIS[selection["index"]],
            detail=selection,
        )

    def _check_title(self, context: Context, image: numpy.ndarray) -> bool:
        """
        检查标题文字"密函报酬选择"是否存在（进入主体的前提条件）

        参数:
        - context: 上下文对象
        - image: 图像数据（BGR 格式 numpy 数组）

        返回值:
        - True: 标题存在，继续识别
        - False: 标题不存在，识别失败
        """
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
            if result and result.hit:
                if result.best_result and isinstance(result.best_result, OCRResult):
                    text = result.best_result.text
                    if text and TITLE_TEXT in text:
                        return True
        except Exception as e:
            logger.error(f"RewardSelector: _check_title 异常 {e}")
        return False

    def _recognize_rewards(
        self, context: Context, image: numpy.ndarray
    ) -> List[Dict[str, Any]]:
        """
        识别三个位置的奖励信息

        参数:
        - context: 上下文对象
        - image: 图像数据（BGR 格式 numpy 数组）

        返回值:
        - [{"rank": "Ⅰ"/"Ⅱ"/"Ⅲ", "icon": "模板名称", "count": 持有数, "position": 0/1/2}]
        """
        rewards = []

        # 识别模板列表（仅武器组）
        icon_templates = [
            Weapon_blueprints,  # 武器图纸
            Weapon_accessories,  # 武器零件
        ]

        for i, card_roi in enumerate(CARD_ROIS):
            reward_info = {"rank": "", "icon": "", "count": 0, "position": i}

            # 识别罗马数字档位
            rank_roi_abs = [
                card_roi[0] + RANK_ROI[0],
                card_roi[1] + RANK_ROI[1],
                card_roi[2] + RANK_ROI[2],
                card_roi[3] + RANK_ROI[3],
            ]
            rank_result = self._ocr_recognition(
                context, rank_roi_abs, ROMAN_RANKS, image
            )
            reward_info["rank"] = rank_result

            # 识别图标
            icon_roi_abs = [
                card_roi[0] + ICON_ROI[0],
                card_roi[1] + ICON_ROI[1],
                card_roi[2] + ICON_ROI[2],
                card_roi[3] + ICON_ROI[3],
            ]
            icon_result = self._template_recognition(
                context, icon_roi_abs, icon_templates, image
            )
            reward_info["icon"] = icon_result

            # 识别持有数
            count_roi_abs = [
                card_roi[0] + COUNT_ROI[0],
                card_roi[1] + COUNT_ROI[1],
                card_roi[2] + COUNT_ROI[2],
                card_roi[3] + COUNT_ROI[3],
            ]
            count_result = self._ocr_count(context, count_roi_abs, image)
            reward_info["count"] = count_result

            rewards.append(reward_info)

        return rewards

    def _ocr_recognition(
        self,
        context: Context,
        roi: List[int],
        expected: List[str],
        image: numpy.ndarray,
    ) -> str:
        """
        OCR文字识别

        参数:
        - context: 上下文对象
        - roi: 识别区域 [x, y, w, h]
        - expected: 期望识别的文字列表
        - image: 图像数据（BGR 格式 numpy 数组）

        返回值:
        - 识别到的文字，未识别到返回空字符串

        执行流程:
        1. 构造 JOCR 参数对象
        2. 调用 run_recognition_direct 执行识别
        3. 从返回的 RecognitionDetail.best_result.text 获取识别文本
        """
        try:
            reco_param = JOCR(
                expected=expected,
                roi=(roi[0], roi[1], roi[2], roi[3]),
            )
            result = context.run_recognition_direct(
                JRecognitionType.OCR,
                reco_param,
                image,
            )
            if result and result.hit:
                if result.best_result and isinstance(result.best_result, OCRResult):
                    text = result.best_result.text
                    if text:
                        return text
        except Exception as e:
            logger.error(f"RewardSelector: _ocr_recognition 异常 {e}")
        return ""

    def _template_recognition(
        self,
        context: Context,
        roi: List[int],
        templates: List[str],
        image: numpy.ndarray,
    ) -> str:
        """
        模板匹配识别

        参数:
        - context: 上下文对象
        - roi: 识别区域 [x, y, w, h]
        - templates: 模板名称列表
        - image: 图像数据（BGR 格式 numpy 数组）

        返回值:
        - 识别到的模板名称，未识别到返回空字符串

        执行流程:
        1. 逐个模板调用 run_recognition_direct 进行 TemplateMatch 识别
        2. 构造 JTemplateMatch 参数对象
        3. 第一个命中的模板名称即为结果
        """
        for template in templates:
            try:
                reco_param = JTemplateMatch(
                    template=[template],
                    roi=(roi[0], roi[1], roi[2], roi[3]),
                    threshold=[0.7],
                )
                result = context.run_recognition_direct(
                    JRecognitionType.TemplateMatch,
                    reco_param,
                    image,
                )
                if result and result.hit:
                    return template
            except Exception as e:
                logger.error(f"RewardSelector: _template_recognition 异常 {e}")
                continue
        return ""

    def _ocr_count(self, context: Context, roi: List[int], image: numpy.ndarray) -> int:
        """
        OCR识别持有数

        参数:
        - context: 上下文对象
        - roi: 识别区域 [x, y, w, h]
        - image: 图像数据（BGR 格式 numpy 数组）

        返回值:
        - 识别到的数字，未识别到返回0

        执行流程:
        1. 构造 JOCR 参数对象，使用 replace 字段去除"持有数"前缀
        2. 调用 run_recognition_direct 执行识别
        3. 从识别文本中提取首个数字作为持有数
        """
        try:
            reco_param = JOCR(
                roi=(roi[0], roi[1], roi[2], roi[3]),
                replace=[
                    ["持有数:", ""],
                    ["持有数：", ""],
                    ["持有数 ", ""],
                    ["持有数", ""],
                ],
            )
            result = context.run_recognition_direct(
                JRecognitionType.OCR,
                reco_param,
                image,
            )
            if (
                result
                and result.best_result
                and isinstance(result.best_result, OCRResult)
            ):
                text = result.best_result.text.strip()
                numbers = re.findall(r"\d+", text)
                if numbers:
                    return int(numbers[0])
        except Exception as e:
            logger.error(f"RewardSelector: _ocr_count 异常 {e}")
        return 0

    def _determine_selection(self, rewards: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        根据奖励信息确定选择位置

        参数:
        - rewards: 三个位置的奖励信息列表

        返回值:
        - {"index": 0/1/2, "category": "weapon/weapon_part/unknown", "ranks": [...], "rewards": [...]}
        """
        icons = [r["icon"] for r in rewards]
        counts = [r["count"] for r in rewards]
        ranks = [r["rank"] for r in rewards]

        # 检测武器图纸 → 选最左侧
        if Weapon_blueprints in icons:
            return {
                "index": 0,
                "category": "weapon",
                "ranks": ranks,
                "rewards": icons,
            }

        # 武器零件优先级逻辑
        part_positions = [
            i for i, icon in enumerate(icons) if icon == Weapon_accessories
        ]

        if part_positions:
            if len(part_positions) == 1:
                # 只有1个零件 → 选该位置
                return {
                    "index": part_positions[0],
                    "category": "weapon_part",
                    "ranks": ranks,
                    "rewards": icons,
                }

            if len(part_positions) >= 2:
                # ≥2个零件 → 选持有数少的
                min_count = min(counts[i] for i in part_positions)
                for i in part_positions:
                    if counts[i] == min_count:
                        return {
                            "index": i,
                            "category": "weapon_part",
                            "ranks": ranks,
                            "rewards": icons,
                        }

        # 兜底 → 选最左侧
        return {
            "index": 0,
            "category": "unknown",
            "ranks": ranks,
            "rewards": icons,
        }
