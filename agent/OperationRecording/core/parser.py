# -*- coding: utf-8 -*-
"""
操作解析器，具有以下功能：
1. 解析普通操作列表
2. 解析时间线操作序列
3. 自动识别模式类型
"""

from typing import List, Dict, Any, Optional, Tuple
from .types import Operation, OperationParam
from utils.logger import logger


class OperationParser:
    """
    操作解析器

    功能说明：
    1. 普通模式
       - parse_operations: 解析操作列表
       - parse_param: 解析完整参数

    2. 时间线模式
       - parse_timeline_sequence: 解析时间线序列
       - is_timeline_sequence: 判断是否为时间线模式

    3. 统一接口
       - parse_unified: 自动识别并解析

    参数格式（普通模式）：
    {
        "operations": [
            {"action": "move", "params": {"direction": "forward"}},
            {"action": "jump", "params": {}}
        ],
        "loop_count": 1
    }

    参数格式（时间线模式）：
    {
        "operations": [
            {"action": "move", "params": {"direction": "left", "duration": 2.0}},
            {"action": "move", "params": {"direction": "forward", "duration": 8.0,
             "overlays": [{"action": "dodge", "params": {"direction": "forward"}, "at": 3.0}]}}
        ],
        "loop_count": 1
    }
    """

    @staticmethod
    def parse_operations(operations_data: List[Dict[str, Any]]) -> List[Operation]:
        """
        解析操作列表（普通模式）

        参数：
        - operations_data: 操作数据列表

        返回：
        - List[Operation]: 解析后的操作列表

        执行流程：
        1. 遍历操作数据
        2. 解析每个操作
        3. 返回操作列表
        """
        operations = []
        for operation_data in operations_data:
            operation = OperationParser._parse_operation(operation_data)
            if operation:
                operations.append(operation)
        return operations

    @staticmethod
    def _parse_operation(operation_data: Dict[str, Any]) -> Optional[Operation]:
        """
        解析单个操作

        参数：
        - operation_data: 操作数据

        返回：
        - Optional[Operation]: 解析后的操作对象，失败返回 None

        执行流程：
        1. 获取动作名称
        2. 获取参数
        3. 创建 Operation 对象
        4. 返回对象或 None
        """
        try:
            action = operation_data.get("action")
            if not action:
                return None

            params = operation_data.get("params", {})
            return Operation(action=action, params=params)
        except Exception as e:
            logger.warning(f"[OperationParser] 解析操作失败: {operation_data}, 错误: {e}")
            return None

    @staticmethod
    def parse_param(param: Dict[str, Any]) -> OperationParam:
        """
        解析操作参数（普通模式）

        参数：
        - param: 参数字典

        返回：
        - OperationParam: 解析后的操作参数对象

        执行流程：
        1. 获取操作列表
        2. 获取循环次数
        3. 解析操作列表
        4. 创建 OperationParam 对象
        """
        operations_data = param.get("operations", [])
        loop_count = param.get("loop_count", 1)

        operations = OperationParser.parse_operations(operations_data)
        return OperationParam(operations, loop_count)

    @staticmethod
    def parse_timeline_sequence(sequence_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        解析时间线序列（高级模式）

        参数：
        - sequence_data: 序列数据列表

        返回：
        - List[Dict[str, Any]]: 解析后的序列数据

        执行流程：
        1. 遍历序列数据
        2. 解析每个序列项
        3. 返回解析后的序列
        """
        parsed_sequence = []

        for item in sequence_data:
            parsed_item = OperationParser._parse_sequence_item(item)
            if parsed_item:
                parsed_sequence.append(parsed_item)

        return parsed_sequence

    @staticmethod
    def _parse_sequence_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        解析单个序列项

        参数：
        - item: 序列项数据

        返回：
        - Optional[Dict[str, Any]]: 解析后的序列项，失败返回 None

        执行流程：
        1. 获取动作名称
        2. 从 params 中获取持续时间和参数
        3. 从 params 中获取叠加动作
        4. 返回解析结果
        """
        try:
            action = item.get("action")
            if not action:
                return None

            params = item.get("params", {}) or {}
            duration = float(params.get("duration", item.get("duration", 0.0)))

            result = {
                "action": action,
                "duration": duration,
                "params": params,
            }

            overlays = params.get("overlays", item.get("overlays", []))
            if overlays and isinstance(overlays, list):
                parsed_overlays = []
                for overlay in overlays:
                    overlay_action = overlay.get("action")
                    if overlay_action:
                        parsed_overlays.append(
                            {
                                "action": overlay_action,
                                "params": overlay.get("params", {}) or {},
                                "at": float(overlay.get("at", 0.0)),
                            }
                        )
                if parsed_overlays:
                    result["overlays"] = parsed_overlays

            return result
        except Exception as e:
            logger.error(f"[OperationParser] 解析序列项失败: {e}")
            return None

    @staticmethod
    def is_timeline_sequence(data: List[Dict[str, Any]]) -> bool:
        """
        判断是否为时间线序列格式

        参数：
        - data: 数据列表

        返回：
        - bool: 是否为时间线模式

        执行流程：
        1. 检查是否为列表
        2. 遍历数据项
        3. 检查是否有 duration 或 overlays 字段（在顶层或 params 中）
        """
        if not isinstance(data, list):
            return False

        for item in data:
            if not isinstance(item, dict):
                continue

            if "duration" in item or "overlays" in item:
                return True

            params = item.get("params", {})
            if isinstance(params, dict) and ("duration" in params or "overlays" in params):
                return True

        return False

    @staticmethod
    def parse_unified(param: Dict[str, Any]) -> Tuple[str, Any]:
        """
        统一解析方法，自动识别格式类型

        参数：
        - param: 参数字典

        返回：
        - Tuple[str, Any]: (模式类型, 解析结果)
          - "timeline": 时间线模式
          - "normal": 普通模式

        执行流程：
        1. 获取操作列表
        2. 判断模式类型
        3. 执行对应解析
        4. 返回结果
        """
        operations_data = param.get("operations", [])

        if OperationParser.is_timeline_sequence(operations_data):
            sequence = OperationParser.parse_timeline_sequence(operations_data)
            loop_count = param.get("loop_count", 1)
            return ("timeline", {"sequence": sequence, "loop_count": loop_count})
        else:
            operation_param = OperationParser.parse_param(param)
            return ("normal", operation_param)

    @staticmethod
    def merge_move_directions(operations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        合并 move 动作的方向

        参数：
        - operations: 原始操作列表

        返回值：
        - List[Dict[str, Any]]: 合并后的操作列表

        说明：
        - 检测所有 move 动作的时间重叠
        - 计算每个时间段的合并方向
        - 生成新的操作序列

        示例：
        输入：
        [
            {"action": "move", "params": {"direction": "forward", "duration": 6}},
            {"action": "move", "params": {"direction": "left", "duration": 3}, "at": 2}
        ]

        输出：
        [
            {"action": "move", "params": {"direction": "forward", "duration": 2}},
            {"action": "move", "params": {"direction": "forward_left", "duration": 3}},
            {"action": "move", "params": {"direction": "forward", "duration": 1}}
        ]
        """
        # 1. 收集所有 move 动作的时间段
        segments = OperationParser._collect_move_segments(operations)

        # 2. 合并重叠的时间段
        merged_segments = OperationParser._merge_overlapping_segments(segments)

        # 3. 生成新的操作序列
        return OperationParser._generate_merged_operations(merged_segments, operations)

    @staticmethod
    def _collect_move_segments(operations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """收集所有 move 动作的时间段"""
        segments = []
        current_time = 0.0

        for op in operations:
            action = op.get("action")
            params = op.get("params", {}) or {}

            if action == "wait":
                duration = params.get("duration", op.get("duration", 1.0))
                current_time += duration
                continue

            if action == "move":
                direction = params.get("direction", "forward")
                duration = params.get("duration", 0)
                overlays = params.get("overlays", op.get("overlays", [])) or []

                # 主动作
                segments.append({
                    "start": current_time,
                    "end": current_time + duration,
                    "directions": {direction}
                })

                # 处理 overlays 中的 move 动作
                for overlay in overlays:
                    overlay_action = overlay.get("action")
                    if overlay_action == "move":
                        overlay_params = overlay.get("params", {}) or {}
                        overlay_direction = overlay_params.get("direction", "forward")
                        overlay_at = float(overlay.get("at", 0))
                        overlay_duration = float(overlay_params.get("duration", overlay.get("duration", 0)))

                        segments.append({
                            "start": current_time + overlay_at,
                            "end": current_time + overlay_at + overlay_duration,
                            "directions": {overlay_direction}
                        })

                current_time += duration
            else:
                duration = params.get("duration", op.get("duration", 0))
                current_time += duration

        return segments

    @staticmethod
    def _merge_overlapping_segments(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """合并重叠的时间段"""
        if not segments:
            return []

        # 按开始时间排序
        segments.sort(key=lambda s: s["start"])

        # 收集所有时间点
        time_points = set()
        for seg in segments:
            time_points.add(seg["start"])
            time_points.add(seg["end"])
        time_points = sorted(time_points)

        # 为每个时间段计算活跃方向
        merged = []
        for i in range(len(time_points) - 1):
            start = time_points[i]
            end = time_points[i + 1]

            # 找出在这个时间段内活跃的所有方向
            active_directions = set()
            for seg in segments:
                if seg["start"] <= start and seg["end"] >= end:
                    active_directions.update(seg["directions"])

            if active_directions:
                # 合并方向
                merged_direction = OperationParser._combine_directions(active_directions)
                merged.append({
                    "start": start,
                    "end": end,
                    "directions": {merged_direction}
                })

        return merged

    @staticmethod
    def _combine_directions(directions: set) -> str:
        """
        合并多个方向为单个方向

        参数：
        - directions: 方向集合

        返回值：
        - str: 合并后的方向

        合并规则：
        - 单个方向：直接返回
        - forward + left -> forward_left
        - forward + right -> forward_right
        - backward + left -> backward_left
        - backward + right -> backward_right
        - 其他组合：按优先级选择
        """
        if len(directions) == 1:
            return directions.pop()

        # 组合方向映射
        combinations = {
            frozenset({"forward", "left"}): "forward_left",
            frozenset({"forward", "right"}): "forward_right",
            frozenset({"backward", "left"}): "backward_left",
            frozenset({"backward", "right"}): "backward_right",
        }

        # 检查是否是有效的组合
        frozen = frozenset(directions)
        if frozen in combinations:
            return combinations[frozen]

        # 无法合并的组合（如 forward + backward），按优先级选择
        priority = {"forward": 4, "backward": 3, "left": 2, "right": 1}
        return max(directions, key=lambda d: priority.get(d, 0))

    @staticmethod
    def _generate_merged_operations(
        merged_segments: List[Dict[str, Any]],
        original_operations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """生成合并后的操作序列"""
        result = []

        for seg in merged_segments:
            direction = seg["directions"].pop()
            duration = seg["end"] - seg["start"]

            if duration > 0:
                result.append({
                    "action": "move",
                    "params": {
                        "direction": direction,
                        "duration": duration
                    }
                })

        return result
