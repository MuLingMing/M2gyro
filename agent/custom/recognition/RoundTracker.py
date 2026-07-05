# -*- coding: utf-8 -*-
"""
轮次追踪识别器

功能说明：
1. 在固定 ROI 内 OCR 识别"当前轮次：xx"文本
2. 提取数字 xx
3. 与类级全局变量 _round_state 中记录的 current_round 比较
4. 若 xx > current_round，更新 _round_state 并返回识别成功
5. 否则返回识别不成功

状态存储：
- current_round 保存在类变量 RoundTracker._round_state 中，按节点名索引
- 生命周期跟随 Python 进程，任务重启后会重置为节点参数中的默认值

兼容变体：
- 冒号可为中文"："或英文":"
- "当前轮次"与数字之间、冒号前后允许存在空格
"""

import json
import re
from typing import Any, Dict, List, Optional, Union

import numpy
from maa.context import Context
from maa.custom_recognition import CustomRecognition
from maa.define import OCRResult, RectType
from maa.pipeline import JOCR, JRecognitionType
from param_merger import ParamMerger
from utils.logger import logger

# 默认识别区域 [x, y, w, h]，基于 720p
DEFAULT_ROI: RectType = [0,200,270,150]

# 默认当前轮次
DEFAULT_CURRENT_ROUND: int = 0

# 最大轮次限制
MAX_ROUND: int = 99

# 全屏 box，用于返回识别成功
SCREEN_BOX: RectType = (0, 0, 1280, 720)

# 轮次文本匹配正则：兼容中英文冒号及空格，冒号可选
_ROUND_PATTERN = re.compile(r"当前轮次[：:\s]*(\d+)")


class RoundTracker(CustomRecognition):
    """
    轮次追踪识别器

    注册方式：通过 agent/custom.json 动态注册

    参数格式（custom_recognition_param）：
    {
        "current_round": 1,           // 当前记录的轮次，默认 1
        "roi": [100, 100, 200, 50],   // 识别区域 [x, y, w, h]，默认 DEFAULT_ROI
        "logger_count": 0             // 输出频率控制，默认 0（不输出）
    }

    状态说明：
    - current_round 保存在类变量 _round_state 中，按节点名索引
    - 生命周期跟随 Python 进程，任务重启后会重置

    字段说明：
    - current_round: 当前记录的轮次阈值，识别到更大的数字时更新
    - roi: OCR 识别区域，基于 720p 坐标
    - logger_count: 输出频率控制，默认 0（不输出）。0 或负数不输出，正整数 N 每 N 轮输出一次（轮次更新时判断）

    返回值：
    - 识别成功且轮次增加:
        box=[0, 0, 1280, 720],
        detail={"hit": True, "current_round": xx, "previous_round": old}
    - 识别失败或轮次未增加:
        box=None,
        detail={"hit": False, "reason": "...", "current_round": current_round, "detected_round": xx}

    Pipeline 使用示例：
    {
        "TrackRound": {
            "recognition": "RoundTracker",
            "custom_recognition_param": {
                "current_round": 1,
                "roi": [100, 100, 200, 50]
            },
            "action": "DoNothing",
            "next": ["处理下一页"]
        }
    }
    """

    # 类级全局状态：节点名 -> 当前轮次
    _round_state: Dict[str, int] = {}

    # 类级全局状态：输出频率控制
    _logger_count: int = 0

    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        """
        执行轮次追踪识别主流程

        参数:
        - context: MaaFramework 上下文对象
        - argv: 识别参数，包含输入图像和 custom_recognition_param

        返回值:
        - CustomRecognition.AnalyzeResult: 识别结果
        """
        image = argv.image

        if image is None or not isinstance(image, numpy.ndarray) or image.size == 0:
            logger.error("RoundTracker: 输入图像无效")
            return CustomRecognition.AnalyzeResult(
                box=None, detail={"hit": False, "reason": "invalid_image"}
            )

        if context.tasker.stopping:
            return CustomRecognition.AnalyzeResult(
                box=None, detail={"hit": False, "reason": "stopping"}
            )

        params = self._parse_params_from_node(context, argv.node_name)
        current_round: int = params["current_round"]
        roi: tuple[int, int, int, int] = params["roi"]
        logger_count: int = params["logger_count"] if params["logger_count"] > 0 else RoundTracker._logger_count

        detected_round = self._recognize_round(context, image, roi)
        if detected_round is None:
            return CustomRecognition.AnalyzeResult(
                box=None,
                detail={
                    "hit": False,
                    "reason": "round_not_recognized",
                    "current_round": current_round,
                },
            )

        # 轮次更新规则：识别到更大轮次，或识别到第 1 轮时均触发更新
        if detected_round > current_round or detected_round == 1:
            RoundTracker._set_current_round(argv.node_name, detected_round)

            # 基于轮次判断是否输出（初次更新或达到指定倍数时输出）
            if logger_count > 0 and (current_round == 0 or self._magnitude(detected_round, logger_count)):
                logger.info(
                    f"当前轮次为 {detected_round}"
                )

            return CustomRecognition.AnalyzeResult(
                box=SCREEN_BOX,
                detail={
                    "hit": True,
                    "current_round": detected_round,
                    "previous_round": current_round,
                },
            )

        return CustomRecognition.AnalyzeResult(
            box=None,
            detail={
                "hit": False,
                "reason": "not_increased",
                "current_round": current_round,
                "detected_round": detected_round,
            },
        )

    @staticmethod
    def _parse_params_from_node(context: Context, node_name: str) -> Dict[str, Any]:
        """
        从节点配置、attach 参数和全局状态中解析参数

        - roi 从节点配置的 custom_recognition_param 读取
        - current_round 从全局状态读取，无记录则使用节点配置的默认值
        - 支持 attach 参数合并（通过 ParamMerger）

        参数:
        - context: 上下文对象
        - node_name: 当前节点名称

        返回值:
        - dict: 包含 current_round、roi 和 logger_count 的字典
        """
        node_data = context.get_node_data(node_name)
        node_reco_param = (
            node_data.get("recognition", {}).get("param", {}) if node_data else {}
        )
        raw_param = node_reco_param.get("custom_recognition_param", {})

        # attach 参数合并
        if isinstance(raw_param, dict) and node_data:
            attach_params = node_data.get("attach", {})
            if attach_params:
                schema = {
                    "current_round": int,
                    "roi": (list, tuple),
                    "logger_count": int,
                }
                raw_param = ParamMerger.merge(
                    "recognition", raw_param, attach_params, schema
                )

        parsed = RoundTracker._parse_params(raw_param)

        parsed["current_round"] = RoundTracker._get_current_round(
            node_name, parsed["current_round"]
        )

        return parsed

    @classmethod
    def _get_current_round(cls, node_name: str, default: int) -> int:
        """
        从类级全局状态读取节点当前轮次

        参数:
        - node_name: 节点名
        - default: 无记录时的默认值

        返回值:
        - int: 当前轮次
        """
        return cls._round_state.get(node_name, default)

    @classmethod
    def _set_current_round(cls, node_name: str, value: int) -> None:
        """
        设置节点当前轮次到类级全局状态

        参数:
        - node_name: 节点名
        - value: 新的轮次数值
        """
        cls._round_state[node_name] = value

    @staticmethod
    def _magnitude(count: int, logger_count: int) -> bool:
        """
        判断是否需要输出轮次状态

        参数:
        - count: 当前轮次
        - logger_count: 输出频率控制参数
          - 0 或负数: 不输出
          - 正整数: 每 logger_count 轮输出一次（含第 1 轮和第 logger_count 轮）

        返回值:
        - bool: 是否需要输出
        """
        if count <= 0 or logger_count <= 0:
            return False
        return count % logger_count == 0 or count == 1 or count == logger_count

    @staticmethod
    def _parse_params(raw_param: Union[str, Dict[str, Any], None]) -> Dict[str, Any]:
        """
        解析 custom_recognition_param 参数

        参数:
        - raw_param: 原始参数，可能为 str（JSON）或 dict

        返回值:
        - dict: 包含 current_round 和 roi 的字典
        """
        params: dict
        if isinstance(raw_param, str):
            try:
                params = json.loads(raw_param) or {}
            except json.JSONDecodeError as e:
                logger.error(f"RoundTracker: 参数解析失败: {e}")
                params = {}
        elif isinstance(raw_param, dict):
            params = raw_param
        else:
            params = {}

        current_round = params.get("current_round", DEFAULT_CURRENT_ROUND)
        roi = params.get("roi", DEFAULT_ROI)
        logger_count = params.get("logger_count", 0)

        try:
            current_round = int(current_round)
        except (ValueError, TypeError):
            current_round = DEFAULT_CURRENT_ROUND

        try:
            logger_count = int(logger_count)
        except (ValueError, TypeError):
            logger_count = 0

        if isinstance(roi, (list, tuple)) and len(roi) == 4:
            try:
                roi = tuple(int(v) for v in roi)
            except (ValueError, TypeError):
                roi = DEFAULT_ROI
        else:
            roi = DEFAULT_ROI

        return {"current_round": current_round, "roi": roi, "logger_count": logger_count}

    @staticmethod
    def _recognize_round(
        context: Context,
        image: numpy.ndarray,
        roi: tuple[int, int, int, int],
    ) -> Optional[int]:
        """
        在指定 ROI 内 OCR 识别"当前轮次：xx"并提取数字

        支持两种 OCR 分词情况：
        1. "当前轮次：xx" 作为一个整体识别结果
        2. "当前轮次" 与数字被拆分为同一行的多个结果

        参数:
        - context: MaaFramework 上下文对象
        - image: 当前帧图像
        - roi: 识别区域 [x, y, w, h]

        返回值:
        - int: 识别到的轮次数字
        - None: 未识别到有效轮次
        """
        try:
            reco_param = JOCR(roi=roi)
            result = context.run_recognition_direct(
                JRecognitionType.OCR, reco_param, image
            )
            if not result or not result.hit or not result.all_results:
                return None

            # 情况 1：单个 OCR 结果直接包含完整文本
            for r in result.all_results:
                if isinstance(r, OCRResult) and r.text:
                    text = r.text.strip().replace(" ", "")
                    match = _ROUND_PATTERN.search(text)
                    if match:
                        detected = int(match.group(1))
                        if detected <= MAX_ROUND:
                            return detected

            # 情况 2：同一行内多个结果被拆分，按行拼接后匹配
            detected = RoundTracker._recognize_by_line(result.all_results)
            if detected is not None and detected <= MAX_ROUND:
                return detected
            return None
        except Exception as e:
            logger.error(f"RoundTracker: OCR 识别异常: {e}")
        return None

    @staticmethod
    def _recognize_by_line(results: list) -> Optional[int]:
        """
        将同一行的 OCR 结果按 x 坐标拼接后再匹配轮次正则

        参数:
        - results: OCR 原始结果列表

        返回值:
        - int: 匹配到的轮次数字
        - None: 未匹配到
        """
        items: List[Dict[str, Any]] = []
        for r in results:
            if not isinstance(r, OCRResult) or not r.text or not r.box:
                continue
            x, y, w, h = RoundTracker._extract_box(r.box)
            text = r.text.strip().replace(" ", "")
            if not text:
                continue
            items.append(
                {
                    "text": text,
                    "x": x,
                    "w": w,
                    "center_y": y + h / 2,
                    "h": h,
                }
            )

        if not items:
            return None

        # 找到包含"轮次"的文本
        round_keyword_item = None
        for item in items:
            if "轮次" in item["text"]:
                round_keyword_item = item
                break

        if not round_keyword_item:
            return None

        # 在包含"轮次"的文本右侧附近查找数字（同一行，且在其右侧）
        keyword_center_y = round_keyword_item["center_y"]
        keyword_x_end = round_keyword_item["x"] + round_keyword_item["w"]
        keyword_h = round_keyword_item["h"]
        y_threshold = max(keyword_h * 0.5, 10)
        x_threshold = keyword_h * 2  # x方向距离阈值，基于文本高度

        # 收集同一行且在"轮次"文本右侧的数字
        nearby_items = []
        for item in items:
            if item is round_keyword_item:
                continue
            # 检查是否在同一行（y坐标接近）
            if abs(item["center_y"] - keyword_center_y) > y_threshold:
                continue
            # 检查是否在右侧（x坐标在关键词右侧附近）
            if item["x"] < keyword_x_end - 5 or item["x"] > keyword_x_end + x_threshold:
                continue
            # 只收集纯数字
            if item["text"].isdigit():
                nearby_items.append(item)

        # 按 x 坐标排序并拼接数字
        nearby_items.sort(key=lambda item: item["x"])
        digits = "".join(item["text"] for item in nearby_items)

        if digits:
            return int(digits)

        return None

    @staticmethod
    def _extract_box(box: Any) -> tuple[int, int, int, int]:
        """
        从 OCR box 中安全提取 [x, y, w, h]

        参数:
        - box: MaaFramework Rect 对象或 list/tuple

        返回值:
        - tuple[int, int, int, int]: x, y, w, h
        """
        if hasattr(box, "x"):
            return (
                int(box.x),
                int(box.y),
                int(box.w),
                int(box.h),
            )
        elif isinstance(box, (list, tuple)) and len(box) >= 4:
            return (
                int(box[0]),
                int(box[1]),
                int(box[2]),
                int(box[3]),
            )
        return 0, 0, 1280, 720
