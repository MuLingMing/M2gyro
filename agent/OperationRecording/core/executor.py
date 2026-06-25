# -*- coding: utf-8 -*-
"""
操作执行器（基于事件队列调度）

所有执行模式（timeline / normal）统一通过 EventScheduler 调度，
消除了原有的双轨执行模型。

功能：
1. 平台初始化与复用
2. 效果管理器初始化
3. 统一执行入口 → JsonAdapter → ActionNode → EventScheduler
"""

from typing import Any, Dict, List, Optional

from maa.context import Context

from .types import OperationParam
from .scheduler import EventScheduler
from .parser import OperationParser
from .config import ConfigManager
from ..platforms import PlatformFactory
from ..effects import EffectManager
from ..json_adapter import JsonAdapter
from utils.logger import logger
import traceback


class OperationExecutor:
    """
    操作执行器

    功能说明：
    1. 初始化
       - _init_platform: 初始化平台
       - _init_effect_manager: 初始化效果管理器

    2. 执行（统一入口）
       - execute_unified: 自动识别模式，统一由 EventScheduler 调度
       - execute: 普通模式
       - execute_timeline: 时间线模式
    """

    def __init__(self, context: Context):
        """
        初始化操作执行器

        参数：
        - context: MAA 上下文对象
        """
        self._context = context
        self._platform = None
        self._config_manager = ConfigManager()
        self._scheduler: Optional[EventScheduler] = None
        self._effect_manager: Optional[EffectManager] = None
        self._init_platform()
        self._init_effect_manager()

    def _init_effect_manager(self):
        """初始化效果管理器"""
        effects_config = self._config_manager.get_effects_config()
        if effects_config:
            self._effect_manager = EffectManager.from_config(effects_config)
        else:
            self._effect_manager = EffectManager()

    def _init_platform(self):
        """初始化平台（PlatformFactory 自带缓存）"""
        if self._context and hasattr(self._context, 'tasker'):
            controller = self._context.tasker.controller
            self._platform = PlatformFactory.create_from_config({}, controller)

    def execute(self, param: OperationParam) -> bool:
        """
        执行操作列表（普通模式，统一走调度器）

        参数：
        - param: 操作参数对象

        返回：
        - bool: 是否成功
        """
        if not self._platform:
            return False

        try:
            for _ in range(param.loop_count):
                operations_data = [{"action": op.action, "params": op.params} for op in param.operations]
                node = JsonAdapter.from_operations(operations_data)
                if not self._run_scheduler(node):
                    return False
            return True
        except Exception as e:
            logger.error(f"[OperationExecutor] execute 异常: {type(e).__name__}: {e}")
            return False

    def execute_unified(self, param: Dict[str, Any]) -> bool:
        """
        统一执行入口

        参数：
        - param: 参数字典

        返回：
        - bool: 是否成功

        执行流程：
        1. 解析参数并识别模式
        2. 根据模式转换 JSON → ActionNode
        3. 统一由 EventScheduler 调度执行
        """
        if not self._platform:
            return False

        try:
            mode, result = OperationParser.parse_unified(param)

            if mode == "timeline":
                sequence = result.get("sequence", [])
                loop_count = result.get("loop_count", 1)
                return self.execute_timeline(sequence, loop_count)
            else:
                return self.execute(result)
        except Exception as e:
            logger.error(f"[OperationExecutor] execute_unified 异常: {type(e).__name__}: {e}")
            return False

    def execute_timeline(
        self, sequence: List[Dict[str, Any]], loop_count: int = 1
    ) -> bool:
        """
        执行时间线序列（统一走调度器）

        参数：
        - sequence: 时间线序列
        - loop_count: 循环次数

        返回：
        - bool: 是否成功
        """
        if not self._platform:
            return False

        try:
            for _ in range(loop_count):
                node = JsonAdapter.from_sequence(sequence)
                if not self._run_scheduler(node):
                    return False
            return True
        except Exception as e:
            logger.error(f"[OperationExecutor] execute_timeline 异常: {type(e).__name__}: {e}")
            logger.error(f"[OperationExecutor] 堆栈信息:\n{traceback.format_exc()}")
            return False

    def _run_scheduler(self, node) -> bool:
        """
        创建并运行事件调度器

        参数：
        - node: ActionNode 根节点

        返回：
        - bool: 是否成功
        """
        self._scheduler = EventScheduler(
            self._platform, self._context, self._effect_manager
        )
        self._scheduler.load(node)
        return self._scheduler.run()

    def get_execution_status(self):
        """获取执行状态"""
        platform_type = "unknown"
        if self._platform is not None:
            platform_type = self._platform.controller_type

        return {
            "platform_type": platform_type,
            "platform_initialized": self._platform is not None,
            "effects_enabled": (
                self._effect_manager.enabled
                if self._effect_manager is not None
                else False
            ),
            "is_running": (
                self._scheduler.is_running
                if self._scheduler is not None
                else False
            ),
        }

    def _execute_operation(self, operation) -> bool:
        """
        执行单个操作（向后兼容，统一走调度器）

        参数：
        - operation: 操作对象

        返回：
        - bool: 是否成功
        """
        if not self._platform:
            return False

        try:
            node = JsonAdapter.from_operations(
                [{"action": operation.action, "params": operation.params}]
            )
            return self._run_scheduler(node)
        except Exception as e:
            logger.error(f"[OperationExecutor] _execute_operation 异常: {type(e).__name__}: {e}")
            return False

    def get_platform(self):
        """获取平台对象"""
        return self._platform

    def get_scheduler(self) -> Optional[EventScheduler]:
        """获取事件调度器"""
        return self._scheduler

    def pause(self):
        """暂停（不支持，事件调度器无暂停机制）"""
        logger.warning("[OperationExecutor] EventScheduler 不支持暂停")

    def resume(self):
        """恢复（不支持，事件调度器无暂停机制）"""
        logger.warning("[OperationExecutor] EventScheduler 不支持恢复")

    def stop(self):
        """停止调度器"""
        if self._scheduler is not None:
            self._scheduler.stop()
