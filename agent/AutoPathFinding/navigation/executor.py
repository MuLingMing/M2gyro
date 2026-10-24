# -*- coding: utf-8 -*-
"""
执行层：把 Decision.commands 翻译为平台操作。

职责：
- 唯一调用 OperationRecording PlatformFactory 的地方（模块间耦合收口）
- 时长单位统一为秒（平台层 turn/move/dodge 已在 P0 修复中统一）
- 大幅转向前按需 release_all
"""

from __future__ import annotations

import time
from typing import List, Optional

from maa.context import Context

from OperationRecording.platforms import PlatformFactory

from utils.logger import logger

from .params import NavigationParams
from .policy import Command, CommandType, Decision, NavPhase


class NavExecutor:
    """导航命令执行器。

    参数:
    - context: MaaFW Context（用于获取 controller）
    """

    def __init__(self, context: Context) -> None:
        self._context = context
        self._platform = None

    def _ensure_platform(self):
        """惰性创建平台适配器（同 controller 复用一份实例）。"""
        if self._platform is None:
            controller = getattr(self._context, "controller", None)
            if controller is None:
                tasker = getattr(self._context, "tasker", None)
                controller = getattr(tasker, "controller", None) if tasker else None
            if controller is None:
                raise RuntimeError("NavExecutor: 无法从 context 获取 controller")
            self._platform = PlatformFactory.create_from_config({}, controller)
        return self._platform

    def reset_platform(self) -> None:
        """释放平台句柄（会话结束时调用）。"""
        self._platform = None

    def execute(self, decision: Decision, params: NavigationParams) -> bool:
        """按序执行决策命令。返回是否全部成功。

        执行中检查 context.tasker.stopping，及时中断。
        """
        if decision.phase in (NavPhase.ARRIVE, NavPhase.FAIL):
            self.release_all()

        for command in decision.commands:
            tasker = getattr(self._context, "tasker", None)
            if tasker is not None and getattr(tasker, "stopping", False):
                logger.info("[NavExecutor] tasker stopping, abort remaining commands")
                return False
            if not self._execute_one(command, params):
                return False
        return True

    def release_all(self) -> bool:
        """释放所有按住的方向/按键。"""
        try:
            platform = self._ensure_platform()
            return bool(platform.release_all())
        except Exception as e:
            logger.warning("[NavExecutor] release_all failed: %s: %s", type(e).__name__, e)
            return False

    def _execute_one(self, command: Command, params: NavigationParams) -> bool:
        """执行单条命令。"""
        platform = self._ensure_platform()
        try:
            if command.release_before:
                platform.release_all()
                time.sleep(params.large_turn_release_s)

            if command.type == CommandType.MOVE:
                return bool(
                    platform.move(
                        command.direction or "forward",
                        command.duration_s or params.move_duration_s,
                    )
                )
            if command.type == CommandType.TURN:
                if command.turn_coordinates is None:
                    return True
                (sx, sy), (ex, ey) = command.turn_coordinates
                return bool(
                    platform.turn(
                        sx,
                        sy,
                        ex,
                        ey,
                        command.duration_s or params.turn_duration_s,
                    )
                )
            if command.type == CommandType.DODGE:
                return bool(
                    platform.dodge(command.direction or params.dodge_direction)
                )
            if command.type == CommandType.INTERACT:
                return bool(platform.interact())
            return True
        except Exception as e:
            logger.warning(
                "[NavExecutor] %s failed: %s: %s",
                command.type.value,
                type(e).__name__,
                e,
            )
            return False
