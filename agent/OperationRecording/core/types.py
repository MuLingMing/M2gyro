# -*- coding: utf-8 -*-
"""
核心数据类型定义

功能：
1. Operation - 封装单一动作及其参数
2. OperationParam - 封装操作列表和循环配置
"""

from typing import Dict, Any, Optional, List


class Operation:
    """
    操作数据结构

    功能说明：
    1. 封装单一动作
       - 存储动作名称
       - 存储动作参数

    参数格式：
    {
        "action": "move",
        "params": {
            "direction": "forward",
            "duration": 1.0
        }
    }

    字段说明：
    - action: 动作名称，必填
    - params: 动作参数，默认为空字典
    """

    def __init__(
        self,
        action: str,
        params: Optional[Dict[str, Any]] = None
    ):
        """
        初始化操作

        参数：
        - action: 动作名称
        - params: 动作参数

        执行流程：
        1. 存储动作名称
        2. 如果参数为空，设置为空字典
        """
        self.action = action
        self.params = params or {}


class OperationParam:
    """
    操作参数数据结构

    功能说明：
    1. 操作列表管理
       - 存储多个 Operation 对象
       - 按顺序执行

    2. 循环配置
       - 设置循环执行次数
       - 默认循环 1 次

    参数格式：
    {
        "operations": [
            {"action": "move", "params": {"direction": "forward"}},
            {"action": "jump", "params": {}}
        ],
        "loop_count": 3
    }

    字段说明：
    - operations: 操作列表，必填
    - loop_count: 循环执行次数，默认 1
    """

    def __init__(self, operations: List[Operation], loop_count: int = 1):
        """
        初始化操作参数

        参数：
        - operations: 操作列表
        - loop_count: 循环执行次数

        执行流程：
        1. 存储操作列表
        2. 存储循环次数
        """
        self.operations = operations
        self.loop_count = loop_count
