# -*- coding: utf-8 -*-
"""
OperationRecording 模块

基于操作录制的动作执行组件，支持不同控制器类型的操作映射。

功能特性：
- 支持普通模式：顺序执行操作列表
- 支持时间线模式：复杂动作序列、并行动作叠加、类人化效果
- 自动模式检测：根据输入格式自动选择执行模式
- 统一模块注册体系：ModuleRegistry 泛型基类
"""

import os
import sys

# 确保 agent/ 目录在 sys.path 中，使得 `from utils.logger import logger` 等
# 相对项目根的导入语句可正常解析（与 agent/main.py 行为一致）
_current_dir = os.path.dirname(os.path.abspath(__file__))
_agent_dir = os.path.dirname(_current_dir)
if _agent_dir not in sys.path:
    sys.path.insert(0, _agent_dir)

from .registry import ModuleRegistry

from .core import (
    OperationExecutor,
    OperationParser,
    EventScheduler,
    ActionEvent,
    ActionNode,
    PrimitiveAction,
    Sequence,
    Parallel,
    AtOffset,
    Operation,
    OperationParam,
    ConfigManager,
)

from .actions import (
    ActionBase,
    TimelineMeta,
    ActionRegistry,
    action_registry,
)

from .effects import (
    EffectBase,
    EffectManager,
    EffectRegistry,
    effect_registry,
    register_effect,
)

from .platforms import (
    PlatformBase,
    KeyboardPlatform,
    TouchPlatform,
    PlatformFactory,
    PlatformRegistry,
    platform_registry,
    register_platform,
)

__all__ = [
    "ModuleRegistry",
    "Operation",
    "OperationParam",
    "ConfigManager",
    "OperationExecutor",
    "OperationParser",
    "EventScheduler",
    "ActionEvent",
    "ActionNode",
    "PrimitiveAction",
    "Sequence",
    "Parallel",
    "AtOffset",
    "ActionBase",
    "TimelineMeta",
    "ActionRegistry",
    "action_registry",
    "EffectBase",
    "EffectManager",
    "EffectRegistry",
    "effect_registry",
    "register_effect",
    "PlatformBase",
    "KeyboardPlatform",
    "TouchPlatform",
    "PlatformFactory",
    "PlatformRegistry",
    "platform_registry",
    "register_platform",
]

# OperationRecordAction 延迟导入，避免循环依赖（actions → core → actions）
from .actions.operation_record_action import OperationRecordAction  # noqa: E402
__all__.append("OperationRecordAction")

__version__ = "4.0.0"
