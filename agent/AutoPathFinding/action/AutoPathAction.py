# -*- coding: utf-8 -*-
"""
自动寻路动作器

功能说明：
1. 识别场景中的目的地标志（门/菱形），执行选择策略，选出最优目标
2. 根据目标位置调整视角、控制角色移动、处理障碍物
3. 内部循环执行直到到达目标或收到停止信号

支持的目标类型：
- gold_door: 金色门（高优先级）
- blue_door: 蓝色门（高优先级）
- red_sword_door: 红色剑形门（中优先级）
- red_door: 红色门（中优先级）
- gold_diamond: 金色菱形（低优先级）

支持的选择策略：
- priority: 按优先级排序，同优先级选最近
- nearest: 始终选择距离最近的目标
- reverse_priority: 反向优先级排序，同优先级选最近

参数格式（JSON）：
{
    "target_types": ["gold_door", "blue_door", "red_sword_door", "red_door"],
    "strategy": "priority",
    "target_priority": {"gold_door": 1, "blue_door": 1, "red_sword_door": 2, "red_door": 2, "gold_diamond": 3},
    "arrival_text": ["归来", "进入"],
    "arrival_distance": 3,
    "distance_roi_offset": [0, -80, 200, 60],
    "text_roi_offset": [0, -120, 300, 80],
    "move_duration": 500,
    "view_adjust_threshold": 100,
    "view_adjust_ratio": 0.3,
    "view_adjust_delay": 0.15,
    "joystick_center": [760, 950],
    "joystick_radius": 80,
    "stuck_detection_frames": 30,
    "stuck_threshold": 100,
    "stuck_retry_count": 3,
    "stuck_search_delay": 0.2,
    "search_rotation_angle": 45,
    "max_loop_count": 100,
    "loop_interval": 0.1,
    "enable_view_adjust": true,
    "enable_stuck_detection": true
}

字段说明：
- target_types: 要识别的目标类型列表，默认全部5种
  - gold_door: 金色门（高优先级）
  - blue_door: 蓝色门（高优先级）
  - red_sword_door: 红色剑形门（中优先级）
  - red_door: 红色门（中优先级）
  - gold_diamond: 金色菱形（低优先级）
- strategy: 目标选择策略，默认 priority
  - priority: 按优先级排序，同优先级选最近的
  - nearest: 始终选择距离最近的目标
  - reverse_priority: 反向优先级排序，同优先级选最近的
- target_priority: 各目标类型的优先级数值，数值越小优先级越高，默认 {gold_door: 1, blue_door: 1, red_sword_door: 2, red_door: 2, gold_diamond: 3}
- arrival_text: 到达判定文字列表，目标旁出现这些文字时判定为已到达（OR 关系），默认 ["归来", "进入"]
- arrival_distance: 到达判定的距离阈值（米），目标旁显示的距离数字小于此值时判定为已到达，默认 3
- distance_roi_offset: 距离数字 OCR 区域偏移 [dx, dy, w, h]，相对于目标中心的偏移量和区域大小，默认 [0, -80, 200, 60]
- text_roi_offset: 到达文字 OCR 区域偏移 [dx, dy, w, h]，相对于目标中心的偏移量和区域大小，默认 [0, -120, 300, 80]
- move_duration: 单次移动操作的持续时间（毫秒），值越大单次移动距离越远，默认 500
- view_adjust_threshold: 视角调整触发阈值（像素），目标偏离屏幕中心超过此值时执行视角调整，默认 100
- view_adjust_ratio: 视角调整比例，实际滑动距离 = 偏移量 × 此比例，默认 0.3
- view_adjust_delay: 视角调整后的等待延迟（秒），用于等待画面响应，默认 0.15
- joystick_center: 虚拟摇杆中心坐标 [x, y]（720p 基准），默认 [760, 950]
- joystick_radius: 虚拟摇杆最大滑动半径（像素），默认 80
- stuck_detection_frames: 卡住检测帧数，连续 N 帧目标位置几乎不变时判定为卡住，默认 30
- stuck_threshold: 卡住检测的位置变化阈值（像素），连续帧间目标位置变化小于此值时累计卡住计数，默认 100
- stuck_retry_count: 卡住后最大重试次数，超过此次数后停止重试，默认 3
- stuck_search_delay: 卡住搜索旋转后的等待延迟（秒），用于等待视角旋转完成，默认 0.2
- search_rotation_angle: 卡住时搜索旋转的角度（度），用于改变视角寻找新路径，默认 45
- max_loop_count: 最大循环次数，寻路循环执行的上限，达到后退出，默认 100
- loop_interval: 循环间隔时间（秒），每次识别-动作循环之间的等待时间，默认 0.1
- enable_view_adjust: 是否启用视角调整，禁用后不会自动滑动屏幕使目标居中，默认 true
- enable_stuck_detection: 是否启用卡住检测，禁用后不会检测和处理卡住情况，默认 true
"""

import json
import math
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from maa.context import Context
from maa.custom_action import CustomAction
from maa.define import BoxAndScoreResult, OCRResult
from maa.pipeline import JActionType, JOCR, JRecognitionType, JTemplateMatch, JSwipe
from utils.logger import logger


@dataclass
class TargetTypeDef:
    """目标类型定义"""
    group: str = ""
    template: str = ""


@dataclass
class DetectedTarget:
    """检测到的目标实例"""
    target_type: str = ""
    box: Tuple[int, int, int, int] = (0, 0, 0, 0)
    center: Tuple[int, int] = (0, 0)
    distance: Optional[float] = None
    arrival_text: Optional[str] = None
    is_arrived: bool = False
    priority: int = 999


TARGET_TYPES: Dict[str, TargetTypeDef] = {
    "gold_door":      TargetTypeDef(group="door",    template="path_target/gold_door.png"),
    "blue_door":      TargetTypeDef(group="door",    template="path_target/blue_door.png"),
    "red_sword_door": TargetTypeDef(group="door",    template="path_target/red_sword_door.png"),
    "red_door":       TargetTypeDef(group="door",    template="path_target/red_door.png"),
    "gold_diamond":   TargetTypeDef(group="special", template="path_target/gold_diamond.png"),
}

DEFAULT_PRIORITY: Dict[str, int] = {
    "gold_door": 1,
    "blue_door": 1,
    "red_sword_door": 2,
    "red_door": 2,
    "gold_diamond": 3,
}

SCREEN_CENTER: Tuple[int, int] = (640, 360)

DISTANCE_PATTERN = r"(\d+(?:\.\d+)?)\s*米"


class AutoPathAction(CustomAction):
    """自动寻路动作器（合并版：识别 + 动作 + 内部循环）"""

    _stuck_counter: int = 0
    _last_target_center: Optional[Tuple[int, int]] = None
    _retry_count: int = 0

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        param = self._parse_param(argv.custom_action_param)
        max_loop = param["max_loop_count"]
        loop_interval = param["loop_interval"]

        for i in range(max_loop):
            if context.tasker.stopping:
                logger.debug("收到停止信号，退出寻路循环")
                self._reset_stuck()
                return False

            image = context.tasker.controller.post_screencap().wait().get()
            detail = self._recognize_and_analyze(context, param, image)

            if detail is None or detail.get("status") == "no_target":
                logger.debug("未检测到目标，继续循环")
                time.sleep(loop_interval)
                continue

            if detail.get("status") == "arrived":
                logger.info(f"已到达目标: {detail.get('target_type')}，原因: {detail.get('arrival_reason')}")
                self._reset_stuck()
                return True

            self._execute_move(context, detail, param)

            time.sleep(loop_interval)

        logger.warning(f"寻路循环达到上限 ({max_loop} 次)，退出")
        self._reset_stuck()
        return True

    def _recognize_and_analyze(
        self,
        context: Context,
        param: Dict[str, Any],
        image: Any,
    ) -> Optional[Dict[str, Any]]:
        detected: List[DetectedTarget] = []
        for target_type in param["target_types"]:
            targets = self._detect_targets(context, target_type, param, image)
            detected.extend(targets)

        if not detected:
            return {"status": "no_target"}

        best = self._select_target(detected, param)

        if best.is_arrived:
            return {
                "status": "arrived",
                "target_type": best.target_type,
                "arrival_reason": "ocr_text" if best.arrival_text else "distance",
                "detected_text": best.arrival_text or "",
                "distance": best.distance,
            }

        offset_x = best.center[0] - SCREEN_CENTER[0]
        offset_y = best.center[1] - SCREEN_CENTER[1]
        direction = self._calculate_direction(offset_x, offset_y)

        return {
            "status": "navigating",
            "target_type": best.target_type,
            "target_center": best.center,
            "distance": best.distance,
            "direction": direction,
            "offset_x": offset_x,
            "offset_y": offset_y,
        }

    def _execute_move(
        self,
        context: Context,
        detail: Dict[str, Any],
        param: Dict[str, Any],
    ) -> None:
        offset_x = detail.get("offset_x", 0)
        offset_y = detail.get("offset_y", 0)
        target_center = detail.get("target_center", SCREEN_CENTER)
        direction = detail.get("direction", "center")

        if param["enable_view_adjust"]:
            self._adjust_view(context, offset_x, offset_y, param)

        if param["enable_stuck_detection"]:
            if self._check_stuck(target_center, param):
                self._handle_stuck(context, param)
                return

        self._move_toward(context, direction, param)

    def _parse_param(self, param_str: Optional[str]) -> Dict[str, Any]:
        if not param_str:
            param_str = "{}"
        try:
            param = json.loads(param_str) if isinstance(param_str, str) else dict(param_str)
        except (json.JSONDecodeError, TypeError):
            param = {}

        return {
            "target_types": param.get("target_types", list(TARGET_TYPES.keys())),
            "strategy": param.get("strategy", "priority"),
            "target_priority": param.get("target_priority", DEFAULT_PRIORITY),
            "arrival_text": param.get("arrival_text", ["归来", "进入"]),
            "arrival_distance": float(param.get("arrival_distance", 3)),
            "distance_roi_offset": param.get("distance_roi_offset", [0, -80, 200, 60]),
            "text_roi_offset": param.get("text_roi_offset", [0, -120, 300, 80]),
            "move_duration": int(param.get("move_duration", 500)),
            "view_adjust_threshold": int(param.get("view_adjust_threshold", 100)),
            "view_adjust_ratio": float(param.get("view_adjust_ratio", 0.3)),
            "view_adjust_delay": float(param.get("view_adjust_delay", 0.15)),
            "joystick_center": param.get("joystick_center", [760, 950]),
            "joystick_radius": int(param.get("joystick_radius", 80)),
            "stuck_detection_frames": int(param.get("stuck_detection_frames", 30)),
            "stuck_threshold": int(param.get("stuck_threshold", 100)),
            "stuck_retry_count": int(param.get("stuck_retry_count", 3)),
            "stuck_search_delay": float(param.get("stuck_search_delay", 0.2)),
            "search_rotation_angle": int(param.get("search_rotation_angle", 45)),
            "max_loop_count": int(param.get("max_loop_count", 100)),
            "loop_interval": float(param.get("loop_interval", 0.1)),
            "enable_view_adjust": param.get("enable_view_adjust", True),
            "enable_stuck_detection": param.get("enable_stuck_detection", True),
        }

    def _detect_targets(
        self,
        context: Context,
        target_type: str,
        param: Dict[str, Any],
        image: Any,
    ) -> List[DetectedTarget]:
        type_def = TARGET_TYPES.get(target_type)
        if type_def is None:
            logger.warning(f"未知目标类型: {target_type}")
            return []

        reco_param = JTemplateMatch(
            template=[type_def.template],
            threshold=[0.7],
        )

        result = context.run_recognition_direct(
            JRecognitionType.TemplateMatch, reco_param, image
        )
        if result is None or not result.hit or not result.all_results:
            return []

        targets: List[DetectedTarget] = []
        priority = param["target_priority"].get(target_type, DEFAULT_PRIORITY.get(target_type, 999))

        for item in result.all_results:
            if not isinstance(item, BoxAndScoreResult) or item.box is None:
                continue
            box = (item.box.x, item.box.y, item.box.w, item.box.h)
            center = (box[0] + box[2] // 2, box[1] + box[3] // 2)

            distance = self._extract_distance(context, center, param, image)
            arrival_text = self._check_arrival_text(context, center, param, image)

            is_arrived = False
            if distance is not None and distance <= param["arrival_distance"]:
                is_arrived = True
            elif arrival_text is not None:
                is_arrived = True

            targets.append(DetectedTarget(
                target_type=target_type,
                box=box,
                center=center,
                distance=distance,
                arrival_text=arrival_text,
                is_arrived=is_arrived,
                priority=priority,
            ))

        return targets

    def _extract_distance(
        self,
        context: Context,
        target_center: Tuple[int, int],
        param: Dict[str, Any],
        image: Any,
    ) -> Optional[float]:
        offset = param["distance_roi_offset"]
        roi = (
            max(0, target_center[0] + offset[0]),
            max(0, target_center[1] + offset[1]),
            offset[2],
            offset[3],
        )

        reco_param = JOCR(
            expected=[DISTANCE_PATTERN],
            roi=roi,
        )

        result = context.run_recognition_direct(JRecognitionType.OCR, reco_param, image)
        if result is None or not result.hit or result.best_result is None:
            return None

        if not isinstance(result.best_result, OCRResult):
            return None

        text = result.best_result.text.strip()
        match = re.search(DISTANCE_PATTERN, text)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        return None

    def _check_arrival_text(
        self,
        context: Context,
        target_center: Tuple[int, int],
        param: Dict[str, Any],
        image: Any,
    ) -> Optional[str]:
        arrival_texts = param["arrival_text"]
        if not arrival_texts:
            return None

        offset = param["text_roi_offset"]
        roi = (
            max(0, target_center[0] + offset[0]),
            max(0, target_center[1] + offset[1]),
            offset[2],
            offset[3],
        )

        reco_param = JOCR(
            expected=arrival_texts,
            roi=roi,
        )

        result = context.run_recognition_direct(JRecognitionType.OCR, reco_param, image)
        if result is None or not result.hit or result.best_result is None:
            return None

        if not isinstance(result.best_result, OCRResult):
            return None

        return result.best_result.text.strip()

    def _select_target(
        self,
        detected: List[DetectedTarget],
        param: Dict[str, Any],
    ) -> DetectedTarget:
        arrived_targets = [t for t in detected if t.is_arrived]
        if arrived_targets:
            return min(arrived_targets, key=lambda t: t.distance if t.distance is not None else 9999)

        strategy = param["strategy"]

        if strategy == "nearest":
            return min(detected, key=lambda t: t.distance if t.distance is not None else 99999)

        reverse = strategy == "reverse_priority"
        sorted_targets = sorted(
            detected,
            key=lambda t: (-t.priority if not reverse else t.priority, t.distance if t.distance is not None else 99999),
        )
        return sorted_targets[0]

    @staticmethod
    def _calculate_direction(offset_x: int, offset_y: int) -> str:
        abs_x = abs(offset_x)
        abs_y = abs(offset_y)

        threshold = 50

        if abs_x < threshold and abs_y < threshold:
            return "center"

        if abs_x > abs_y * 2:
            return "right" if offset_x > 0 else "left"

        if abs_y > abs_x * 2:
            return "down" if offset_y > 0 else "up"

        directions = []
        if offset_x > threshold:
            directions.append("right")
        elif offset_x < -threshold:
            directions.append("left")

        if offset_y > threshold:
            directions.append("down")
        elif offset_y < -threshold:
            directions.append("up")

        return "_".join(directions) if directions else "center"

    def _adjust_view(
        self,
        context: Context,
        offset_x: int,
        offset_y: int,
        param: Dict[str, Any],
    ) -> None:
        threshold = param["view_adjust_threshold"]
        ratio = param["view_adjust_ratio"]

        adjust_x = 0
        adjust_y = 0

        if abs(offset_x) > threshold:
            adjust_x = -int(offset_x * ratio)

        if abs(offset_y) > threshold:
            adjust_y = -int(offset_y * ratio)

        if adjust_x == 0 and adjust_y == 0:
            return

        screen_cx, screen_cy = SCREEN_CENTER
        swipe = JSwipe()
        swipe.begin = (screen_cx, screen_cy, 1, 1)
        swipe.end = [(screen_cx + adjust_x, screen_cy + adjust_y, 1, 1)]
        swipe.duration = [300]

        context.run_action_direct(JActionType.Swipe, swipe)
        time.sleep(param["view_adjust_delay"])

    def _move_toward(
        self,
        context: Context,
        direction: str,
        param: Dict[str, Any],
    ) -> None:
        if direction == "center":
            return

        center = tuple(param["joystick_center"])
        radius = param["joystick_radius"]
        duration = param["move_duration"]

        direction_map = {
            "up": (0, -1),
            "down": (0, 1),
            "left": (-1, 0),
            "right": (1, 0),
            "up_left": (-0.707, -0.707),
            "up_right": (0.707, -0.707),
            "down_left": (-0.707, 0.707),
            "down_right": (0.707, 0.707),
        }

        vec = direction_map.get(direction)
        if vec is None:
            return

        end_x = int(center[0] + vec[0] * radius)
        end_y = int(center[1] + vec[1] * radius)

        swipe = JSwipe()
        swipe.begin = (center[0], center[1], 1, 1)
        swipe.end = [(end_x, end_y, 1, 1)]
        swipe.duration = [duration]

        context.run_action_direct(JActionType.Swipe, swipe)

    def _check_stuck(
        self,
        target_center: Tuple[int, int],
        param: Dict[str, Any],
    ) -> bool:
        if self._last_target_center is None:
            self._last_target_center = target_center
            self._stuck_counter = 0
            return False

        dx = target_center[0] - self._last_target_center[0]
        dy = target_center[1] - self._last_target_center[1]
        distance_sq = dx * dx + dy * dy

        threshold = param["stuck_threshold"]

        if distance_sq < threshold * threshold:
            self._stuck_counter += 1
        else:
            self._stuck_counter = 0

        self._last_target_center = target_center

        return self._stuck_counter >= param["stuck_detection_frames"]

    def _handle_stuck(self, context: Context, param: Dict[str, Any]) -> None:
        self._retry_count += 1

        if self._retry_count >= param["stuck_retry_count"]:
            logger.warning(f"卡住重试次数已达上限 ({param['stuck_retry_count']})")
            self._reset_stuck()
            return

        angle = param["search_rotation_angle"]
        screen_cx, screen_cy = SCREEN_CENTER

        swipe = JSwipe()
        swipe.begin = (screen_cx, screen_cy, 1, 1)
        swipe.end = [(screen_cx + int(200 * math.sin(math.radians(angle))), screen_cy, 1, 1)]
        swipe.duration = [400]

        context.run_action_direct(JActionType.Swipe, swipe)
        time.sleep(param["stuck_search_delay"])

        self._stuck_counter = 0
        self._last_target_center = None
        logger.debug(f"检测到卡住，执行搜索旋转 (第 {self._retry_count} 次)")

    def _reset_stuck(self) -> None:
        self._stuck_counter = 0
        self._last_target_center = None
        self._retry_count = 0
