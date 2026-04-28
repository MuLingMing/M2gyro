# -*- coding: utf-8 -*-
"""
操作参数数据结构定义，具有以下功能：
1. 封装操作列表
2. 支持循环执行配置
"""

from typing import List
from .operation import Operation


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
