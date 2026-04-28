# -*- coding: utf-8 -*-
"""
操作执行器，具有以下功能：
1. 普通模式执行操作列表
2. 时间线模式执行复杂序列
3. 支持停止响应，释放按键
4. 平台自动检测和初始化
"""

from typing import List, Optional, Dict, Any
from maa.context import Context
from ..action_types import Operation, OperationParam
from ..platforms import PlatformFactory
from ..actions import action_registry
from ..config import ConfigManager
from .timeline_manager import ActionTimeline
from .humanizer import humanizer
from .operation_parser import OperationParser


class OperationExecutor:
    """
    操作执行器

    功能说明：
    1. 初始化
       - _init_platform: 初始化平台
       - _init_humanizer: 初始化类人化

    2. 执行
       - execute: 普通模式执行
       - execute_timeline: 时间线模式执行
       - execute_unified: 统一执行入口

    3. 工具
       - _detect_controller_type: 检测控制器类型
       - get_execution_status: 获取执行状态
       - get_platform: 获取平台对象

    参数格式（时间线模式）：
    {
        "operations": [
            {"action": "move", "params": {"direction": "left"}, "duration": 2.0}
        ],
        "loop_count": 1
    }
    """

    def __init__(self, context: Context):
        """
        初始化操作执行器

        参数：
        - context: MAA 上下文对象

        执行流程：
        1. 保存上下文
        2. 初始化平台
        3. 初始化类人化
        4. 初始化时间线
        """
        self._context = context
        self._platform = None
        self._config_manager = ConfigManager()
        self._timeline = None
        self._init_platform()
        self._init_humanizer()

    def _init_platform(self):
        """
        初始化平台

        执行流程：
        1. 获取控制器
        2. 检测控制器类型
        3. 创建平台对象
        """
        if self._context and hasattr(self._context, 'tasker'):
            controller = self._context.tasker.controller
            controller_type = self._detect_controller_type(controller)
            self._platform = PlatformFactory.create_platform(controller_type, controller)

    def _init_humanizer(self):
        """
        初始化类人化

        执行流程：
        1. 读取配置
        2. 应用配置到全局 humanizer
        """
        humanizer_config = self._config_manager.get('humanization', {})

        if humanizer_config.get('enabled', True):
            humanizer.enabled = True
            humanizer.reaction_time_ms = (
                humanizer_config.get('reaction_time_ms', {}).get('min', 80),
                humanizer_config.get('reaction_time_ms', {}).get('max', 200)
            )
            humanizer.action_gap_ms = (
                humanizer_config.get('action_gap_ms', {}).get('min', 30),
                humanizer_config.get('action_gap_ms', {}).get('max', 150)
            )
            humanizer.acceleration_factor = humanizer_config.get('acceleration_factor', 0.15)
            humanizer.deceleration_factor = humanizer_config.get('deceleration_factor', 0.15)
        else:
            humanizer.enabled = False

    def _detect_controller_type(self, controller):
        """
        检测控制器类型

        参数：
        - controller: 控制器对象

        返回：
        - str: 平台类型（"adb" 或 "win32"）

        执行流程：
        1. 检查 controller name
        2. 检查 controller config
        3. 检查 controller uuid
        4. 默认返回 adb
        """
        if controller is None:
            return 'adb'

        if hasattr(controller, 'name'):
            name = str(controller.name).lower()
            if 'adb' in name or 'android' in name:
                return 'adb'
            elif 'win32' in name or 'windows' in name:
                return 'win32'

        if hasattr(controller, 'config'):
            config = controller.config
            if isinstance(config, dict):
                if config.get('type') == 'adb':
                    return 'adb'
                if 'adb_path' in config or 'adb_serial' in config:
                    return 'adb'

        if hasattr(controller, 'uuid'):
            uuid = str(getattr(controller, 'uuid', '')).lower()
            if 'adb' in uuid or 'emulator' in uuid:
                return 'adb'

        return 'adb'

    def execute(self, param: OperationParam) -> bool:
        """
        执行操作列表（普通模式）

        参数：
        - param: 操作参数对象

        返回：
        - bool: 是否成功

        执行流程：
        1. 检查平台是否初始化
        2. 循环执行次数
        3. 依次执行每个操作
        """
        if not self._platform:
            return False

        try:
            for _ in range(param.loop_count):
                for operation in param.operations:
                    if not self._execute_operation(operation):
                        return False
            return True
        except Exception:
            return False

    def execute_unified(self, param: Dict[str, Any]) -> bool:
        """
        统一执行入口

        参数：
        - param: 参数字典

        返回：
        - bool: 是否成功

        执行流程：
        1. 检查平台是否初始化
        2. 解析参数并识别模式
        3. 根据模式执行
        """
        if not self._platform:
            return False

        try:
            mode, result = OperationParser.parse_unified(param)

            if mode == "timeline":
                sequence = result.get("sequence", [])
                loop_count = result.get("loop_count", 1)
                return self.execute_timeline(sequence, loop_count, context=self._context)
            else:
                return self.execute(result)
        except Exception:
            return False

    def execute_timeline(self, sequence: List[Dict[str, Any]], loop_count: int = 1, test_mode: bool = False, context: Optional[Context] = None) -> bool:
        """
        执行时间线序列

        参数：
        - sequence: 时间线序列
        - loop_count: 循环次数，默认 1
        - test_mode: 测试模式，默认 False
        - context: MAA 上下文对象

        返回：
        - bool: 是否成功

        执行流程：
        1. 检查平台是否初始化
        2. 循环执行次数
        3. 创建并启动时间线
        4. 循环更新时间线，检查停止
        5. 收到停止时释放按键
        """
        if not self._platform:
            return False

        try:
            for _ in range(loop_count):
                self._timeline = ActionTimeline(self._platform)

                if test_mode or not humanizer.enabled:
                    self._timeline.set_test_mode(True)

                self._timeline.from_sequence(sequence)
                self._timeline.start()

                while self._timeline.get_status()['is_running']:
                    if context is not None and getattr(context.tasker, 'stopping', False):
                        self._platform.release_all()
                        self._timeline.stop()
                        return False
                    self._timeline.update()
                    if not test_mode and humanizer.enabled:
                        import time
                        time.sleep(0.01)

            return True
        except Exception:
            return False

    def get_execution_status(self):
        """
        获取执行状态

        返回：
        - Dict[str, Any]: 执行状态

        执行流程：
        1. 收集平台信息
        2. 收集时间线信息
        3. 返回完整状态
        """
        platform_type = "unknown"
        if self._platform is not None:
            platform_type = getattr(self._platform, '_controller_type', 'unknown')

        timeline_status = None
        if self._timeline is not None:
            timeline_status = self._timeline.get_status()

        return {
            "platform_type": platform_type,
            "platform_initialized": self._platform is not None,
            "humanizer_enabled": humanizer.enabled,
            "timeline_status": timeline_status
        }

    def _execute_operation(self, operation: Operation) -> bool:
        """
        执行单个操作

        参数：
        - operation: 操作对象

        返回：
        - bool: 是否成功

        执行流程：
        1. 检查平台是否初始化
        2. 从注册表创建动作
        3. 添加类人化延迟
        4. 执行动作
        """
        if not self._platform:
            return False

        try:
            action = action_registry.create_action(operation.action, self._platform)
            if not action:
                return False

            if humanizer.enabled:
                humanizer.human_delay()

            return action.execute(operation.params)
        except Exception:
            return False

    def get_platform(self):
        """
        获取平台对象

        返回：
        - PlatformBase | None: 平台对象
        """
        return self._platform

    def get_timeline(self) -> Optional[ActionTimeline]:
        """
        获取时间线对象

        返回：
        - ActionTimeline | None: 时间线对象
        """
        return self._timeline

    def pause_timeline(self):
        """暂停时间线"""
        if self._timeline:
            self._timeline.pause()

    def resume_timeline(self):
        """恢复时间线"""
        if self._timeline:
            self._timeline.resume()

    def stop_timeline(self):
        """停止时间线"""
        if self._timeline:
            self._timeline.stop()
