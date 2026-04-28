# -*- coding: utf-8 -*-
"""
OperationRecording 模块

基于操作录制的动作执行组件，支持不同控制器类型的操作映射。

功能特性：
- 支持普通模式：顺序执行操作列表
- 支持时间线模式：复杂动作序列、并行动作叠加、类人化效果
- 自动模式检测：根据输入格式自动选择执行模式
"""

from .action_types import (
    Operation,
    OperationParam,
)

from .core import (
    OperationExecutor,
    OperationParser,
    ActionTimeline,
    TimedAction,
    ActionPriority,
    Humanizer,
    humanizer,
)

from .actions import (
    ActionBase,
    ActionRegistry,
    action_registry,
)

__all__ = [
    # Types
    "Operation",
    "OperationParam",
    # Core
    "OperationExecutor",
    "OperationParser",
    "ActionTimeline",
    "TimedAction",
    "ActionPriority",
    "Humanizer",
    "humanizer",
    # Actions
    "ActionBase",
    "ActionRegistry",
    "action_registry",
]

# 延迟导入 OperationRecordAction
from .actions.operation_record_action import OperationRecordAction
__all__.append("OperationRecordAction")

__version__ = "1.2.0"
