# -*- coding: utf-8 -*-
"""
自动寻路模块

架构说明：
- PathFindingReco: 识别器，识别游戏画面中的目标图标，计算方向和距离
- PathFinderAction: 动作器，根据识别结果执行移动操作，验证移动有效性
- TargetSelector: 目标选择器接口，支持插件式扩展

支持的选择器：
- PriorityTargetSelector: 按模板优先级选择目标
- NearestTargetSelector: 按距离最近选择目标
- CompositeTargetSelector: 按类型优先级+距离组合选择

支持的平台（复用 OperationRecording 的平台层）：
- ADB (Android): 虚拟摇杆 + 视角滑动
- Win32 (PC): 方向键
"""

from .action.path_finder_action import PathFinderAction
from .recognition.path_finding_reco import PathFindingReco
from .selector import (
    CompositeTargetSelector,
    NearestTargetSelector,
    PriorityTargetSelector,
    TargetInfo,
    TargetSelector,
)

__all__ = [
    "PathFindingReco",
    "PathFinderAction",
    "TargetSelector",
    "TargetInfo",
    "PriorityTargetSelector",
    "NearestTargetSelector",
    "CompositeTargetSelector",
]
