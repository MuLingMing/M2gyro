# -*- coding: utf-8 -*-
"""
决策层（纯函数状态机）。

状态: SEARCH → TRACK → APPROACH → RECOVER → ARRIVE / FAIL
- 纯函数 decide()：输入 Observation + NavigationParams，输出 Decision
- 无 IO、无时间依赖（时间量由调用方测好传入），便于单元测试
- 决策到命令的翻译由 executor 完成，policy 只描述"意图"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

from .estimator import MovementState
from .geometry import (
    TURN_CLIP_HORIZONTAL,
    TurnGrade,
    angle_diff,
    compute_heading_turn_coordinates,
    compute_scan_turn_coordinates,
)
from .params import NavigationParams


class NavPhase(Enum):
    """导航状态机相位（单一赋值来源，修复旧版两处赋值互相覆盖）。"""

    SEARCH = "search"
    TRACK = "track"
    APPROACH = "approach"
    RECOVER = "recover"
    ARRIVE = "arrive"
    FAIL = "fail"


class CommandType(Enum):
    """命令类型（executor 按此分派平台调用）。"""

    MOVE = "move"
    TURN = "turn"
    DODGE = "dodge"
    INTERACT = "interact"
    NONE = "none"


@dataclass
class Command:
    """单条执行命令。"""

    type: CommandType
    direction: Optional[str] = None
    duration_s: Optional[float] = None
    turn_coordinates: Optional[Tuple[Tuple[int, int], Tuple[int, int]]] = None
    turn_grade: TurnGrade = TurnGrade.FINE_TUNE
    release_before: bool = False


@dataclass
class Decision:
    """一次决策的完整输出。

    - phase: 当前相位（pipeline 可据此分支，如 ARRIVE→交互节点，FAIL→告警）
    - commands: 按序执行的命令列表（可为空，表示本帧只观察）
    """

    phase: NavPhase
    commands: List[Command] = field(default_factory=list)
    detail: dict = field(default_factory=dict)


def decide(
    state: MovementState,
    params: NavigationParams,
    stuck_duration_ms: int,
    elapsed_ms: int,
    locked: bool,
) -> Decision:
    """状态机主入口（纯函数）。

    参数:
    - state: 估计器输出的当帧状态
    - params: 导航参数
    - stuck_duration_ms: 已持续卡住时长（由 estimator.stuck 测得后传入）
    - elapsed_ms: 会话累计时长（超时保护用）
    - locked: 当帧是否有锁定目标

    返回值:
    - Decision
    """
    # ---- ARRIVE ----
    if state.distance is not None and state.distance <= params.arrival_distance:
        commands: List[Command] = []
        if params.interact_on_arrive:
            commands.append(Command(type=CommandType.INTERACT))
        return Decision(
            phase=NavPhase.ARRIVE,
            commands=commands,
            detail={"distance": state.distance},
        )

    # ---- FAIL：卡住超时（stuck_timeout_ms 修复后在此生效）----
    if stuck_duration_ms > params.stuck_timeout_ms:
        return Decision(
            phase=NavPhase.FAIL,
            commands=[],
            detail={"stuck_duration_ms": stuck_duration_ms},
        )

    # ---- RECOVER：卡住（未超时）→ 脱困动作 ----
    # 修复旧版：STUCK 仅在 action 里隐式 dodge，无独立相位
    if state.distance is not None and _is_stuck_frame(state, params):
        return Decision(
            phase=NavPhase.RECOVER,
            commands=[
                Command(
                    type=CommandType.DODGE,
                    direction=params.recover_dodge_direction,
                    duration_s=params.dodge_release_s,
                )
            ],
            detail={"stuck_duration_ms": stuck_duration_ms},
        )

    # ---- SEARCH：无目标且未锁定（锁定丢失帧按 TRACK 处理走转向找回） ----
    if state.target is None and not locked:
        # 有朝向反馈：固定步长环视，累计转角有界；转满仍未发现 → FAIL（不再无限盲走）
        if state.heading_valid and params.enable_turning:
            if state.cumulative_turn_deg >= params.search_scan_deg:
                return Decision(
                    phase=NavPhase.FAIL,
                    commands=[],
                    detail={
                        "search_exhausted": True,
                        "cumulative_turn_deg": round(state.cumulative_turn_deg, 1),
                    },
                )
            sign = 1 if state.turn_attempt % 2 == 0 else -1
            coords = compute_scan_turn_coordinates(
                params.search_scan_step_deg * params.turn_px_per_deg,
                sign,
                TURN_CLIP_HORIZONTAL,
            )
            if coords is not None:
                return Decision(
                    phase=NavPhase.SEARCH,
                    commands=[
                        Command(
                            type=CommandType.TURN,
                            turn_coordinates=coords,
                            turn_grade=TurnGrade.LARGE_TURN,
                            duration_s=params.turn_duration_s,
                        )
                    ],
                    detail={"scan_sign": sign, "cumulative_turn_deg": round(state.cumulative_turn_deg, 1)},
                )
        # 无朝向反馈：沿用旧逻辑（坐标偏移环视或短程前进）
        commands = []
        if params.enable_turning and state.turn_coordinates is not None:
            commands.append(
                Command(
                    type=CommandType.TURN,
                    turn_coordinates=state.turn_coordinates,
                    turn_grade=TurnGrade.LARGE_TURN,
                    duration_s=params.turn_duration_s,
                )
            )
        else:
            commands.append(
                Command(
                    type=CommandType.MOVE,
                    direction="forward",
                    duration_s=params.move_duration_near_s,
                )
            )
        return Decision(phase=NavPhase.SEARCH, commands=commands)

    # ---- 距离缺失 + 已对准：无法判断远近，走短程默认移动 ----
    if state.distance is None:
        if state.in_dead_zone:
            return Decision(
                phase=NavPhase.APPROACH,
                commands=[
                    Command(
                        type=CommandType.MOVE,
                        direction="forward",
                        duration_s=params.move_duration_s,
                    )
                ],
                detail={"distance_missing": True, "locked": locked},
            )
        # 距离缺失且偏心：只转向不前进
        turn_cmd = _turn_command(state, params, in_place=True)
        if turn_cmd is not None:
            return Decision(
                phase=NavPhase.TRACK,
                commands=[turn_cmd],
                detail={"distance_missing": True, "turn_attempt": state.turn_attempt},
            )
        return Decision(phase=NavPhase.TRACK, commands=[])

    # ---- 有目标有距离 ----
    commands = []
    # 偏心超死区：先转向（大幅转向前先松键）
    if not state.in_dead_zone:
        turn_cmd = _turn_command(state, params, in_place=False)
        if turn_cmd is not None:
            commands.append(turn_cmd)
    # 死区内或微调后仍前进
    commands.append(
        Command(
            type=CommandType.MOVE,
            direction=state.direction or "forward",
            duration_s=_resolve_move_duration(state.distance, params),
        )
    )
    phase = NavPhase.APPROACH if state.in_dead_zone else NavPhase.TRACK
    return Decision(phase=phase, commands=commands, detail={"distance": state.distance})


def _is_stuck_frame(state: MovementState, params: NavigationParams) -> bool:
    """是否处于卡住状态（连续帧计数达到阈值）。"""
    return state.stuck_frames >= params.stuck_threshold


def _turn_command(
    state: MovementState,
    params: NavigationParams,
    in_place: bool,
):
    """生成转向命令。

    有朝向反馈（heading_valid）：P 控制器按 (目标角-当前朝向) 误差计算转向量，
    行进/原地双限幅（MaaEnd-2 steering_controller 参数），死区内不转。
    无朝向反馈：回退旧 offset 经验式（turn_coordinates 由 controller 预计算）。

    参数:
    - in_place: 是否原地转向（距离缺失只转不走时限幅更宽）
    """
    if not params.enable_turning:
        return None
    if (
        state.heading_valid
        and state.heading is not None
        and state.target_angle is not None
    ):
        turn_needed = angle_diff(state.target_angle, state.heading)
        if abs(turn_needed) <= params.steer_deadband_deg:
            return None
        cmd_deg = params.steer_kp * turn_needed
        limit = (
            params.steer_max_deg_in_place
            if in_place
            else params.steer_max_deg_moving
        )
        cmd_deg = max(-limit, min(limit, cmd_deg))
        coords = compute_heading_turn_coordinates(
            cmd_deg, TURN_CLIP_HORIZONTAL, params.turn_px_per_deg
        )
        if coords is None:
            return None
        grade = (
            TurnGrade.LARGE_TURN
            if abs(turn_needed) >= params.rotation_upper_threshold
            else TurnGrade.FINE_TUNE
        )
        return Command(
            type=CommandType.TURN,
            turn_coordinates=coords,
            turn_grade=grade,
            duration_s=params.turn_duration_s,
            release_before=grade == TurnGrade.LARGE_TURN,
        )
    if state.turn_coordinates is not None:
        grade = state.turn_grade
        return Command(
            type=CommandType.TURN,
            turn_coordinates=state.turn_coordinates,
            turn_grade=grade,
            duration_s=params.turn_duration_s,
            release_before=grade == TurnGrade.LARGE_TURN,
        )
    return None


def _resolve_move_duration(distance: int, params: NavigationParams) -> float:
    """按距离线性插值移动时长（秒）。移植旧 _resolve_duration 并统一单位。"""
    far = params.distance_far
    near = params.distance_near
    if far <= near:
        return params.move_duration_s
    if distance >= far:
        duration = params.move_duration_far_s
    elif distance <= near:
        duration = params.move_duration_near_s
    else:
        ratio = (distance - near) / (far - near)
        duration = params.move_duration_near_s + ratio * (
            params.move_duration_far_s - params.move_duration_near_s
        )
    if params.max_move_time_s > 0 and duration > params.max_move_time_s:
        duration = params.max_move_time_s
    return duration
