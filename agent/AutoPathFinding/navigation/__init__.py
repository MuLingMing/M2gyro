# -*- coding: utf-8 -*-
"""
导航模块（AutoPathFinding 重构版）。

分层：Perception(感知) → Estimator(估计) → Policy(决策, 纯函数) → Executor(执行)
会话：NavigationController 按 node_name 管理会话生命周期。
"""

from .controller import NavigationController, NavigationSession, controller
from .estimator import LockedTarget, MovementState, RotationAdjuster, StuckDetector, TargetEstimator
from .executor import NavExecutor
from .geometry import (
    DIRECTIONS_8,
    DIR_CENTER_ANGLE_8,
    SCREEN_CENTER,
    TURN_CLIP_HORIZONTAL,
    TURN_CLIP_VERTICAL,
    TurnGrade,
    angle_diff,
    bin_direction,
    classify_turn,
    compute_heading_turn_coordinates,
    compute_scan_turn_coordinates,
    compute_target_angle,
    compute_turn_coordinates,
    deviation_angle,
)
from .minimap import MinimapObservation, MinimapTracker
from .params import NavigationParams
from .perception import ScreenPerceiver
from .policy import Command, CommandType, Decision, NavPhase, decide

__all__ = [
    "NavigationController",
    "NavigationSession",
    "controller",
    "NavigationParams",
    "ScreenPerceiver",
    "TargetEstimator",
    "MovementState",
    "LockedTarget",
    "RotationAdjuster",
    "StuckDetector",
    "NavExecutor",
    "MinimapTracker",
    "MinimapObservation",
    "Command",
    "CommandType",
    "Decision",
    "NavPhase",
    "decide",
    "TurnGrade",
    "SCREEN_CENTER",
    "DIRECTIONS_8",
    "DIR_CENTER_ANGLE_8",
    "angle_diff",
    "bin_direction",
    "classify_turn",
    "compute_target_angle",
    "compute_turn_coordinates",
    "deviation_angle",
]
