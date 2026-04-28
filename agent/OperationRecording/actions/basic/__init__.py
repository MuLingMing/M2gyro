# -*- coding: utf-8 -*-
"""
基础动作模块

包含所有基础动作类，通过 @register_action 装饰器自动注册。
"""

from .move_action import MoveAction
from .jump_action import JumpAction
from .dodge_action import DodgeAction
from .turn_action import TurnAction
from .interact_action import InteractAction
from .charge_attack_action import ChargeAttackAction
from .crouch_action import CrouchAction
from .wait_action import WaitAction

__all__ = ["MoveAction", "JumpAction", "DodgeAction", "TurnAction", "InteractAction", "ChargeAttackAction", "CrouchAction", "WaitAction"]
