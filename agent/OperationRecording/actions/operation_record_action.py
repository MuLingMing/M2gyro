# -*- coding: utf-8 -*-
"""
OperationRecordAction，MaaFramework Custom Action 入口点。

功能说明：
1. 作为 MaaFramework 的自定义动作接口
2. 解析 JSON 格式的操作参数
3. 创建执行器并执行操作序列
4. 支持普通模式和时间线模式两种执行方式
"""

import json
from typing import Optional
from maa.context import Context
from maa.custom_action import CustomAction
from ..action_types import OperationParam
from ..core.operation_executor import OperationExecutor
from ..core.operation_parser import OperationParser


class OperationRecordAction(CustomAction):
    """操作录制动作类
    
    功能说明：
    1. MaaFramework 自定义动作实现
    2. 接收并解析 JSON 格式的操作参数
    3. 自动识别执行模式（普通/时间线）
    4. 创建执行器并执行操作序列
    5. 支持停止响应（通过执行器的 release_all）
    
    参数格式：
    {
        "custom_action": "OperationRecordAction",
        "custom_action_param": {
            "operations": [
                {"action": "move", "params": {"direction": "forward", "duration": 1.0}}
            ],
            "loop_count": 1
        }
    }
    
    支持的动作列表：
    通用动作参数：
    - duration: 动作持续时间（秒，时间线模式参数）
    - overlays: 叠加动作列表（可选，时间线模式参数）

    1. move - 移动动作
       参数：
       - direction: 方向 ("forward"/"backward"/"left"/"right")
    2. jump - 跳跃动作
    3. dodge - 闪避动作
       参数：
       - direction: 方向（可选，"forward"/"backward"/"left"/"right"）
    4. turn - 转向动作
       参数：
       - angle: 角度（正数向右转，负数向左转）
    5. interact - 交互动作
       参数：
       - interaction_type: 交互类型（可选，默认 "default"）
    6. charge_attack - 蓄力攻击动作
       参数：
       - x: 目标X坐标（可选）
       - y: 目标Y坐标（可选）
    7. crouch - 下蹲动作
    8. spiral_leap - 螺旋飞跃动作
    9. wait - 等待动作
       参数：
       - duration: 等待时间（秒，默认 1.0）
       - until: 目标时间点（秒，相对于时间线开始，仅限时间线模式）
         - 如果提供了 until，则忽略 duration
         - 如果当前时间 >= until，则不等待
    
    叠加动作列表格式（可选，时间线模式参数）：
    - overlays: 叠加动作列表，每个包含：
       - action: 动作名称
       - params: 动作参数
       - at: 开始时间点（秒，相对于主动作开始）
    
    字段说明：
    - _executor: 操作执行器实例
    """

    def __init__(self):
        """初始化操作录制动作
        
        执行流程：
        1. 调用父类初始化
        2. 初始化执行器引用为 None
        """
        super().__init__()
        self._executor: Optional[OperationExecutor] = None

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        """执行操作录制动作
        
        参数：
        - context: MAA 上下文对象
        - argv: 运行参数，包含 custom_action_param
        
        返回：
        - bool: 是否执行成功
        
        执行流程：
        1. 解析 JSON 格式的参数字符串
        2. 创建 OperationExecutor 实例
        3. 使用 OperationParser 解析参数（验证格式）
        4. 调用 execute_unified 执行操作序列
        5. 捕获 JSON 解析错误和其他异常
        6. 返回执行结果
        """
        try:
            custom_action_param = json.loads(argv.custom_action_param)

            self._executor = OperationExecutor(context)

            OperationParser.parse_unified(custom_action_param)

            success = self._executor.execute_unified(custom_action_param)

            return success

        except json.JSONDecodeError:
            return False
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False