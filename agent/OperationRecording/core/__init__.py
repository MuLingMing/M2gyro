# -*- coding: utf-8 -*-
"""
OperationRecording 核心模块
"""

from .executor import OperationExecutor
from .parser import OperationParser
from .scheduler import EventScheduler
from .event import ActionEvent
from .node import ActionNode, PrimitiveAction, Sequence, Parallel, AtOffset
from .types import Operation, OperationParam
from .config import ConfigManager

# 向后兼容别名（仍导出旧名，但指向新实现的类或提示废弃）
# ActionTimeline/TimedAction/ActionPriority/ActionState 已被 EventScheduler/ActionEvent 替代

__all__ = [
    "OperationExecutor",
    "OperationParser",
    "EventScheduler",
    "ActionEvent",
    "ActionNode",
    "PrimitiveAction",
    "Sequence",
    "Parallel",
    "AtOffset",
    "Operation",
    "OperationParam",
    "ConfigManager",
]