# -*- coding: utf-8 -*-
"""
操作解析器，具有以下功能：
1. 解析普通操作列表
2. 解析时间线操作序列
3. 自动识别模式类型
"""

from typing import List, Dict, Any, Optional, Tuple
from ..action_types import Operation, OperationParam


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
            {"action": "move", "params": {"direction": "left"}, "duration": 2.0},
            {"action": "move", "params": {"direction": "forward"}, "duration": 8.0,
             "overlays": [{"action": "dodge", "params": {"direction": "forward"}, "at": 3.0}]}
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
        except Exception:
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
        2. 获取持续时间和参数
        3. 解析叠加动作
        4. 返回解析结果
        """
        try:
            action = item.get("action")
            if not action:
                return None

            result = {
                "action": action,
                "duration": float(item.get("duration", 0.0)),
                "params": item.get("params", {}) or {}
            }

            # 解析叠加动作
            overlays = item.get("overlays", [])
            if overlays and isinstance(overlays, list):
                parsed_overlays = []
                for overlay in overlays:
                    overlay_action = overlay.get("action")
                    if overlay_action:
                        parsed_overlays.append({
                            "action": overlay_action,
                            "params": overlay.get("params", {}) or {},
                            "at": float(overlay.get("at", 0.0))
                        })
                if parsed_overlays:
                    result["overlays"] = parsed_overlays

            return result
        except Exception as e:
            print(f"Error parsing sequence item: {e}")
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
        3. 检查是否有 duration 或 overlays 字段
        """
        if not isinstance(data, list):
            return False

        for item in data:
            if not isinstance(item, dict):
                continue

            # 检查是否包含时间线特征字段
            if "duration" in item or "overlays" in item:
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
        # 检查是否为时间线模式
        operations_data = param.get("operations", [])

        if OperationParser.is_timeline_sequence(operations_data):
            # 时间线模式
            sequence = OperationParser.parse_timeline_sequence(operations_data)
            loop_count = param.get("loop_count", 1)
            return ("timeline", {"sequence": sequence, "loop_count": loop_count})
        else:
            # 普通模式
            operation_param = OperationParser.parse_param(param)
            return ("normal", operation_param)
