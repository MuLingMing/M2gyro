# -*- coding: utf-8 -*-
"""
委托密函关卡选择识别器

功能说明：
1. 根据区域参数按优先级检查 角色/武器/魔之楔 三个区域
2. 识别各区域的持有数，持有数为 0 则跳过该区域
3. 在持有数 > 0 的区域中识别关卡名称，匹配自定义关卡列表
4. 按关卡优先级选取最优关卡，返回其 ROI
5. 所有区域均不满足条件时调用 post_stop() 终止任务链

单次 OCR + 最近 Tab 分类策略：
- 在 UNIFIED_ROI 区域执行一次 OCR，获取所有文本结果
- 从结果中提取 Tab 标签（角色/武器/魔之楔）的 X 坐标作为区域中心
- 每个 OCR 结果按 X 坐标分配到最近的 Tab 中心所属区域
- 同一区域内提取持有数（数字）和关卡名称（子串匹配）

选择优先级（三级筛选）：
① 区域优先级（REGION_PRIORITY 常量）
   - 决定区域检查顺序，与 region_types 取交集后按此顺序遍历
② 区域持有数（> 0 才参与）
   - 过滤掉不可用的区域（持有数为 0 或无法识别）
③ 关卡优先级（STAGE_PRIORITY 常量）
   - 在同一区域的多个命中关卡中选优先级最高的

文件内常量：
- REGION_PRIORITY: 区域优先级（从高到低），决定检查顺序
- STAGE_PRIORITY: 关卡优先级（从高到低），决定同区域多关卡选取顺序
- UNIFIED_ROI: 统一 OCR 搜索区域（720p 基准），所有识别均在此范围内
- FALLBACK_TAB_X: 动态布局降级时使用的硬编码 Tab 中心 X 坐标

返回值（兼容 IfElseAction）：
- 类型1 命中关卡: AnalyzeResult(box=关卡ROI, detail={hit=True, hit_node="if", region, stage, ...})
- 类型2 页面正确但无命中: AnalyzeResult(box=[0,0,0,0], detail={hit=True, hit_node="else", ...})
- 类型3 未识别到页面: AnalyzeResult(box=None, detail={hit=False, ...})
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy
from maa.context import Context
from maa.custom_recognition import CustomRecognition
from maa.define import OCRResult
from maa.pipeline import JOCR, JRecognitionType
from utils.logger import logger

REGION_PRIORITY: List[str] = ["角色", "武器", "魔之楔"]
STAGE_PRIORITY: List[str] = ["探险", "驱离", "扼守"]

_REGION_INDEX: Dict[str, int] = {name: i for i, name in enumerate(REGION_PRIORITY)}

UNIFIED_ROI: List[int] = [280, 60, 1000, 660]

FALLBACK_TAB_X: Dict[str, int] = {
    "角色": 570,
    "武器": 850,
    "魔之楔": 1135,
}

VALID_REGIONS = {"角色", "武器", "魔之楔"}

TITLE_TEXT: str = "刷新密函委托"
TITLE_ROI: List[int] = [400, 600, 300, 120]

REGION_ATTACH_MAP: Dict[str, str] = {
    "region_0": "角色",
    "region_1": "武器",
    "region_2": "魔之楔",
}

STAGE_ATTACH_MAP: Dict[str, str] = {
    "stage_0": "探险",
    "stage_1": "驱离",
    "stage_2": "扼守",
}


class CovertStage(CustomRecognition):
    """
    委托密函关卡选择识别器

    注册方式：通过 agent/custom.json 动态注册，不引入装饰器

    参数来源（优先级从高到低）：
    1. 节点 attach（由 interface checkbox 选项注入）
       - region_0/1/2 → 角色/武器/魔之楔
       - stage_0/1/2 → 探险/驱离/扼守
       - 空 attach 时回退到 custom_recognition_param
    2. custom_recognition_param（直接调用时使用）

    custom_recognition_param 格式：
    {
        "region_types": ["角色", "武器", "魔之楔"],
        "stage_list": ["驱离", "探险", "扼守"]
    }

    字段说明：
    - region_types: 要检查的区域列表（1~3 个），值为 "角色"/"武器"/"魔之楔" 的子集。
                  若为空或全非法，默认使用 REGION_PRIORITY 全部区域
    - stage_list: 自定义关卡名称列表，仅匹配这些关卡（子串匹配：识别文字包含关键字即命中）。
                 注意：列表中的名称不应存在包含关系（如 "探" 和 "探险"），否则可能导致误匹配。
                 支持 Pipeline attach 覆盖。为空时直接终止任务链

    关卡优先级：
    - 使用 STAGE_PRIORITY 常量（探险 > 驱离 > 扼守），在同一区域命中多个关卡时按此顺序选取

    单次 OCR + 最近 Tab 分类策略：
    - 在 UNIFIED_ROI 区域执行一次 OCR，获取所有文本结果
    - 从结果中提取 Tab 标签的 X 坐标作为区域中心
    - 每个 OCR 结果按 X 坐标分配到最近的 Tab 中心所属区域
    - 同一区域内提取持有数和关卡名称

    核心能力：
    - 按区域优先级遍历 角色/武器/魔之楔 三个区域
    - 对每个区域检查持有数，> 0 才继续
    - 在可用区域内识别关卡名称，与 stage_list 子串匹配
    - 按关卡优先级选取最优结果返回 ROI
    - 所有区域不满足时终止任务链
    """

    def __init__(self) -> None:
        super().__init__()
        self._parsed_params_cache: Optional[Dict[str, Any]] = None
        self._parsed_params_raw: Any = None

    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        """
        执行关卡选择识别主流程

        参数:
        - context: MaaFramework 上下文对象，用于调用 OCR 和控制任务链
        - argv: 识别参数，包含输入图像和 custom_recognition_param

        返回值（兼容 IfElseAction）:
        - CustomRecognition.AnalyzeResult:
            类型1 命中关卡: box=选中关卡的 ROI，detail 包含 hit=True/hit_node="if"/区域/关卡/持有数等信息
            类型2 页面正确但无命中: box=[0,0,0,0]，detail 包含 hit=True/hit_node="else"
            类型3 未识别到页面: box=None，detail 包含 hit=False

        执行流程:
        1. 校验输入图像有效性（非空、numpy 数组、size > 0）
        2. 检查 stopping 信号，收到则立即返回
        3. 标题检测：OCR 检查 TITLE_ROI 区域是否包含"刷新密函委托"，未识别到则提前返回 hit=False
        4. 优先从节点 attach 读取 checkbox 选项，无 attach 则回退 custom_recognition_param
        5. 校验 stage_list 非空，为空则 post_stop 终止
        6. 计算 effective_regions（region_types ∩ REGION_PRIORITY，保持优先级顺序）
        7. 单次 OCR → 最近 Tab 分类 → 提取持有数和关卡
        8. 按区域优先级遍历：
           a. 跳过持有数 <= 0 或无法识别的区域
           b. 跳过无命中关卡的区域
           c. 第一个满足条件的区域，按 STAGE_PRIORITY 选最优关卡并返回
        9. 所有区域均不满足 → 根据 tabs_found_count 区分：
           a. tabs_found_count == 3（页面正确但无命中）→ 返回 box=[0,0,0,0]
           b. tabs_found_count < 3（未识别到页面）→ 返回 box=None
        """
        image = argv.image

        if image is None or not isinstance(image, numpy.ndarray) or image.size == 0:
            logger.error("CovertStage: 输入图像无效")
            return CustomRecognition.AnalyzeResult(
                box=None, detail={"hit": False, "reason": "invalid_image"}
            )

        if context.tasker.stopping:
            return CustomRecognition.AnalyzeResult(
                box=None, detail={"hit": False, "reason": "stopping"}
            )

        if not self._check_title(context, image):
            return CustomRecognition.AnalyzeResult(
                box=None, detail={"hit": False, "reason": "title_not_found"}
            )

        node_data = context.get_node_data(argv.node_name) or {}
        attach = node_data.get("attach", {})

        if attach:
            region_types, stage_list = self._read_options_from_attach(attach)
        else:
            params = self._parse_params(argv.custom_recognition_param)
            region_types = params["region_types"]
            stage_list = params["stage_list"]

        if not stage_list:
            # logger.warning("CovertStage: stage_list 为空")
            context.tasker.post_stop()
            return CustomRecognition.AnalyzeResult(
                box=None,
                detail={"hit": False, "terminated": True, "reason": "empty_stage_list"},
            )

        effective_regions = [r for r in REGION_PRIORITY if r in region_types]

        if not effective_regions:
            # logger.warning("CovertStage: 无有效区域，终止任务链")
            context.tasker.post_stop()
            return CustomRecognition.AnalyzeResult(
                box=None,
                detail={
                    "hit": False,
                    "terminated": True,
                    "reason": "no_effective_regions",
                },
            )

        ocr_items = self._do_unified_ocr(context, image)
        counts, stages, is_dynamic, tabs_found_count = self._classify_all(ocr_items, stage_list)

        checked_regions: List[Dict[str, Any]] = []
        for region in effective_regions:
            if context.tasker.stopping:
                return CustomRecognition.AnalyzeResult(
                    box=None, detail={"hit": False, "reason": "stopping"}
                )

            held_count = counts.get(region)
            if held_count is None or held_count <= 0:
                checked_regions.append(
                    {
                        "region": region,
                        "held_count": held_count,
                        "reason": "zero_or_unreadable",
                    }
                )
                continue

            matched_stages = stages.get(region, [])
            if not matched_stages:
                checked_regions.append(
                    {
                        "region": region,
                        "held_count": held_count,
                        "reason": "no_stage_matched",
                    }
                )
                continue

            best_stage = self._select_best_stage(matched_stages, STAGE_PRIORITY)

            # logger.info(
            #     f"CovertStage: 命中区域={region} 关卡={best_stage['name']} "
            #     f"持有数={held_count}"
            # )
            return CustomRecognition.AnalyzeResult(
                box=best_stage["box"],
                detail={
                    "hit": True,
                    "hit_node": "if",
                    "region": region,
                    "stage": best_stage["name"],
                    "held_count": held_count,
                    "region_index": _REGION_INDEX[region],
                    "stage_priority_index": self._get_stage_priority(
                        best_stage["name"], STAGE_PRIORITY
                    ),
                    "all_matched_stages": [s["name"] for s in matched_stages],
                    "layout_dynamic": is_dynamic,
                },
            )

        if tabs_found_count == 3:
            return CustomRecognition.AnalyzeResult(
                box=[0, 0, 0, 0],
                detail={
                    "hit": True,
                    "hit_node": "else",
                    "reason": "all_regions_exhausted",
                    "checked_regions": checked_regions,
                    "tabs_found_count": tabs_found_count,
                },
            )

        return CustomRecognition.AnalyzeResult(
            box=None,
            detail={
                "hit": False,
                "reason": "all_regions_exhausted",
                "checked_regions": checked_regions,
                "tabs_found_count": tabs_found_count,
            },
        )

    @staticmethod
    def _check_title(context: Context, image: numpy.ndarray) -> bool:
        """检查标题文字 '刷新密函委托' 是否存在，不存在则说明不在目标页面"""
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
                f"CovertStage: _check_title 异常 error={e}", exc_info=True
            )
        return False

    @staticmethod
    def _read_options_from_attach(attach: dict) -> Tuple[List[str], List[str]]:
        """
        从节点 attach 中读取 checkbox 选项参数

        attach 键名映射（避免同名覆盖）：
        - region_0/1/2 → 角色/武器/魔之楔
        - stage_0/1/2 → 探险/驱离/扼守

        参数:
        - attach: 节点的 attach 字典

        返回值:
        - Tuple[regions, stages]:
            regions: 选中的区域列表，空则回退 REGION_PRIORITY
            stages: 选中的关卡列表，空则回退 STAGE_PRIORITY
        """
        regions = [r for key, r in REGION_ATTACH_MAP.items() if attach.get(key)]
        stages = [s for key, s in STAGE_ATTACH_MAP.items() if attach.get(key)]

        if not regions:
            regions = list(REGION_PRIORITY)
        if not stages:
            stages = list(STAGE_PRIORITY)

        return regions, stages

    def _parse_params(self, raw_param: str | dict | None) -> Dict[str, Any]:
        """
        解析 custom_recognition_param 参数（带缓存）

        参数:
        - raw_param: 原始参数，可能为 str（JSON）或 dict

        返回值:
        - dict: 包含 "region_types"、"stage_list" 两个键的字典
               region_types 已过滤非法值，为空时默认全部区域
               stage_list 保持原样传入

        解析规则:
        - str 类型 → json.loads 解析（捕获 JSONDecodeError）
        - dict 类型 → 直接使用
        - 其他 → 返回空字典
        - region_types 中非法值会被过滤，全非法时使用 REGION_PRIORITY 默认值
        - 同一 raw_param 引用（is 判断）直接返回缓存结果
        - stage_list 中存在包含关系时发出警告
        """
        if (
            raw_param is self._parsed_params_raw
            and self._parsed_params_cache is not None
        ):
            return self._parsed_params_cache

        if isinstance(raw_param, str):
            try:
                params = json.loads(raw_param)
            except json.JSONDecodeError as e:
                logger.error(f"CovertStage: 参数解析失败: {e}")
                params = {}
        elif isinstance(raw_param, dict):
            params = raw_param
        else:
            params = {}

        region_types = params.get("region_types", [])
        stage_list = params.get("stage_list", [])

        region_types = [r for r in region_types if r in VALID_REGIONS]
        if not region_types:
            region_types = list(REGION_PRIORITY)

        self._validate_stage_list(stage_list)

        result = {
            "region_types": region_types,
            "stage_list": stage_list,
        }

        self._parsed_params_raw = raw_param
        self._parsed_params_cache = result
        return result

    @staticmethod
    def _validate_stage_list(stage_list: List[str]) -> None:
        """
        校验 stage_list 中是否存在包含关系，存在则发出警告

        参数:
        - stage_list: 关卡名称列表
        """
        for i, s1 in enumerate(stage_list):
            for j, s2 in enumerate(stage_list):
                if i != j and s1 in s2:
                    logger.warning(
                        f"CovertStage: stage_list 中存在包含关系 "
                        f"'{s1}' ⊂ '{s2}'，可能导致误匹配"
                    )

    def _do_unified_ocr(
        self, context: Context, image: numpy.ndarray
    ) -> List[Dict[str, Any]]:
        """
        在 UNIFIED_ROI 区域执行一次 OCR，返回所有有效结果

        每个 OCR 结果提取为字典：
        - text: 识别文本（已 strip）
        - box_x: X 坐标（> 0，用于区域分类）
        - box: [x, y, w, h] 矩形框（用于返回 ROI）

        参数:
        - context: MaaFramework 上下文对象
        - image: 当前帧图像

        返回值:
        - List[Dict]: OCR 结果列表，OCR 异常时返回空列表
        """
        items: List[Dict[str, Any]] = []

        try:
            reco_param = JOCR(
                roi=(
                    UNIFIED_ROI[0],
                    UNIFIED_ROI[1],
                    UNIFIED_ROI[2],
                    UNIFIED_ROI[3],
                ),
            )
            result = context.run_recognition_direct(
                JRecognitionType.OCR, reco_param, image
            )
            if result and result.hit and result.all_results:
                for r in result.all_results:
                    if isinstance(r, OCRResult) and r.text and r.box:
                        box_x = self._extract_box_x(r.box)
                        if box_x is None:
                            continue
                        box = (
                            [r.box.x, r.box.y, r.box.w, r.box.h]
                            if hasattr(r.box, "x")
                            else list(r.box)
                        )
                        items.append(
                            {
                                "text": r.text.strip(),
                                "box_x": box_x,
                                "box": box,
                            }
                        )
        except Exception as e:
            logger.error(f"CovertStage: 统一 OCR 异常 error={e}")

        # logger.debug(f"CovertStage: OCR 识别到 {len(items)} 个结果")
        return items

    def _classify_all(
        self,
        ocr_items: List[Dict[str, Any]],
        stage_list: List[str],
    ) -> Tuple[Dict[str, Optional[int]], Dict[str, List[Dict[str, Any]]], bool, int]:
        """
        从 OCR 结果中一步完成：找 Tab → 分配区域 → 提取持有数和关卡

        分类策略：最近 Tab 中心
        - 从 OCR 结果中提取 Tab 标签（角色/武器/魔之楔）的 X 坐标作为区域中心
        - 每个 OCR 结果按 X 坐标分配到最近的 Tab 中心所属区域
        - 识别到 2 个 Tab 时推断缺失 Tab 位置
        - 识别到 0~1 个 Tab 时降级到硬编码 Tab 中心

        参数:
        - ocr_items: 统一 OCR 的结果列表
        - stage_list: 待匹配的关卡名称列表

        返回值:
        - Tuple[counts, stages, is_dynamic, tabs_found_count]:
            counts: {区域名: 持有数或None}
            stages: {区域名: [{name, box}, ...]}
            is_dynamic: 是否为动态检测结果
            tabs_found_count: 实际从 OCR 中识别到的 Tab 标签数量（推断前，0~3）
        """
        tab_positions: Dict[str, int] = {}

        for item in ocr_items:
            for label in VALID_REGIONS:
                if label in item["text"] and label not in tab_positions:
                    tab_positions[label] = item["box_x"]
                    break

        tabs_found_count = len(tab_positions)
        is_dynamic = tabs_found_count >= 2

        if is_dynamic:
            if len(tab_positions) == 2:
                self._infer_missing_tab(tab_positions)
            sorted_tabs = sorted(tab_positions.items(), key=lambda x: x[1])
            # logger.debug(f"[CovertStage] 动态 Tab 位置 {tab_positions}")
        else:
            missing = VALID_REGIONS - set(tab_positions.keys())
            logger.warning(f"[CovertStage] Tab 标签识别不足 2 个（缺少 {missing}），使用降级位置")
            sorted_tabs = sorted(FALLBACK_TAB_X.items(), key=lambda x: x[1])

        counts: Dict[str, Optional[int]] = {r: None for r in VALID_REGIONS}
        stages_by_region: Dict[str, List[Dict[str, Any]]] = {
            r: [] for r in VALID_REGIONS
        }
        seen_names: Dict[str, set] = {r: set() for r in VALID_REGIONS}
        held_label_items: List[Dict[str, Any]] = []
        region_candidates: Dict[str, List[Dict[str, Any]]] = {r: [] for r in VALID_REGIONS}

        for item in ocr_items:
            region = self._find_nearest_region(item["box_x"], sorted_tabs)
            if region is None:
                continue

            text = item["text"]
            matched_stage = False
            seen = seen_names.get(region, set())
            for expected in stage_list:
                if expected in text and expected not in seen:
                    seen.add(expected)
                    stages_by_region[region].append(
                        {
                            "name": expected,
                            "box": item["box"],
                        }
                    )
                    matched_stage = True
                    break

            if not matched_stage:
                count_match = re.search(r"持有数\s*(\d+)", text)
                if count_match and region in VALID_REGIONS:
                    counts[region] = int(count_match.group(1))
                elif re.fullmatch(r"持有数", text.strip()) and region in VALID_REGIONS:
                    held_label_items.append(
                        {"region": region, "box_y": item["box"][1]}
                    )
                elif re.fullmatch(r"\d+", text.strip()) and region in VALID_REGIONS:
                    region_candidates[region].append(
                        {
                            "value": int(text.strip()),
                            "box": item["box"],
                            "box_y": item["box"][1],
                        }
                    )

        for label in held_label_items:
            region = label["region"]
            if counts[region] is not None:
                continue
            label_y = label["box_y"]
            best_digit: Optional[int] = None
            best_dist = 9999
            for candidate in region_candidates[region]:
                dist = abs(candidate["box_y"] - label_y)
                if dist < best_dist:
                    best_dist = dist
                    best_digit = candidate["value"]
            if best_digit is not None:
                counts[region] = best_digit
                logger.debug(
                    "[CovertStage] 持有数关联: region=%s label_y=%s digit=%s dist=%s",
                    region,
                    label_y,
                    best_digit,
                    best_dist,
                )

        missing_counts = [r for r in VALID_REGIONS if counts.get(r) is None]
        if missing_counts:
            logger.warning("[CovertStage] 持有数读取缺失区域: %s", missing_counts)

        # logger.debug("[CovertStage] 分类结果: counts=%s stages=%s", counts, stages_by_region)
        return counts, stages_by_region, is_dynamic, tabs_found_count

    @staticmethod
    def _find_nearest_region(
        x: int, sorted_tabs: List[Tuple[str, int]]
    ) -> Optional[str]:
        """
        根据 X 坐标找到最近的 Tab 中心，返回对应区域名

        参数:
        - x: OCR 识别结果的 X 坐标
        - sorted_tabs: 按 X 排序的 [(区域名, Tab中心X), ...]

        返回值:
        - str: 区域名（"角色"/"武器"/"魔之楔"）
        - None: sorted_tabs 为空
        """
        if not sorted_tabs:
            return None

        nearest = sorted_tabs[0][0]
        min_dist = abs(x - sorted_tabs[0][1])
        for label, tab_x in sorted_tabs[1:]:
            dist = abs(x - tab_x)
            if dist < min_dist:
                min_dist = dist
                nearest = label
        return nearest

    @staticmethod
    def _infer_missing_tab(tab_positions: Dict[str, int]) -> None:
        """
        根据已识别的 2 个 Tab 推断缺失 Tab 的位置（原地修改 tab_positions）

        推断规则：
        - 缺失左侧 Tab → 左侧 = 最左已知 - 平均间距
        - 缺失右侧 Tab → 右侧 = 最右已知 + 平均间距
        - 缺失中间 Tab → 中间 = 左右已知的平均值

        参数:
        - tab_positions: 已识别的 Tab 位置字典（恰好 2 项），会被原地修改添加第 3 项
        """
        missing = VALID_REGIONS - set(tab_positions.keys())
        if not missing:
            return
        missing_name = next(iter(missing))

        sorted_known = sorted(tab_positions.items(), key=lambda item: item[1])
        known_xs = [pos for _, pos in sorted_known]
        spacing = known_xs[1] - known_xs[0]

        missing_idx = REGION_PRIORITY.index(missing_name)
        if missing_idx == 0:
            inferred_x = known_xs[0] - spacing
        elif missing_idx == len(REGION_PRIORITY) - 1:
            inferred_x = known_xs[1] + spacing
        else:
            inferred_x = (known_xs[0] + known_xs[1]) // 2

        tab_positions[missing_name] = inferred_x
        # logger.info(
        #     f"CovertStage: 推断缺失 Tab '{missing_name}' 位置 x={inferred_x}"
        # )

    @staticmethod
    def _extract_box_x(box: Any) -> Optional[int]:
        """
        从 OCR 结果的 box 对象中安全提取 X 坐标

        支持两种 box 格式：
        - 属性访问式：box.x（MaaFramework Box 对象）
        - 序列索引式：box[0]（list/tuple）

        参数:
        - box: OCR 识别结果的 box 对象

        返回值:
        - int: X 坐标值（> 0）
        - None: 无法提取或值为 0（避免 X=0 被误分类到左侧区域）
        """
        val: Optional[int] = None
        if hasattr(box, "x"):
            val = int(box.x)
        elif isinstance(box, (list, tuple)) and len(box) >= 1:
            val = int(box[0])

        if val is not None and val > 0:
            return val
        return None

    @staticmethod
    def _select_best_stage(
        matched: List[Dict[str, Any]], priority_list: List[str]
    ) -> Dict[str, Any]:
        """
        按优先级从多个匹配的关卡中选取优先级最高的

        选择逻辑：
        - priority_list 为空 → 返回 matched[0]（第一个命中的）
        - priority_list 非空 → 构建 name→stage 映射，按优先级顺序查找
        - priority_list 中无任何匹配 → 兜底返回 matched[0]

        参数:
        - matched: 当前区域中命中的关卡列表，每项含 name 和 box
        - priority_list: 关卡优先级列表（从高到低）

        返回值:
        - Dict: 优先级最高的关卡条目 {"name": str, "box": [x,y,w,h]}

        前置条件:
        - matched 非空（调用方已保证）
        """
        if not priority_list:
            return matched[0]

        name_map = {s["name"]: s for s in matched}
        for name in priority_list:
            if name in name_map:
                return name_map[name]

        return matched[0]

    @staticmethod
    def _get_stage_priority(name: str, priority_list: List[str]) -> int:
        """
        获取关卡名在优先级列表中的索引位置

        参数:
        - name: 关卡名称
        - priority_list: 关卡优先级列表

        返回值:
        - int: 索引位置（0-based），不在列表中时返回 -1
        """
        try:
            return priority_list.index(name)
        except ValueError:
            return -1
