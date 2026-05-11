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

from .registry import ModuleRegistry

from .core import (
    OperationExecutor,
    OperationParser,
    ActionTimeline,
    TimedAction,
    ActionPriority,
    ActionState,
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
    "ActionTimeline",
    "TimedAction",
    "ActionPriority",
    "ActionState",
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

__version__ = "3.0.0"
