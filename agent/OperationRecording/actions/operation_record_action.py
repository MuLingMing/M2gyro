# -*- coding: utf-8 -*-
"""
OperationRecordAction，MaaFramework Custom Action 入口点
"""

import json
from typing import Optional
from maa.context import Context
from maa.custom_action import CustomAction
from ..action_types import OperationParam
from ..core.operation_executor import OperationExecutor
from ..core.operation_parser import OperationParser


class OperationRecordAction(CustomAction):
    """
    操作录制动作类
    """

    def __init__(self):
        super().__init__()
        self._executor: Optional[OperationExecutor] = None

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        """
        执行操作录制动作
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