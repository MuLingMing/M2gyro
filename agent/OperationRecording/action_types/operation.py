# -*- coding: utf-8 -*-
"""
操作数据结构定义，具有以下功能：
1. 封装单一动作及其参数
2. 提供简洁的操作初始化接口
"""

from typing import Dict, Any, Optional


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
