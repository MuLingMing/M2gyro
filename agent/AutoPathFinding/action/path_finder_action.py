# -*- coding: utf-8 -*-
"""
自动寻路执行器

根据前序 PathFindingReco 返回的识别结果（direction），执行移动操作。
复用 OperationRecording 的 PlatformFactory，自动适配 ADB/Desktop 平台。

功能说明：
1. 从 argv.reco_detail.best_result.detail 获取识别结果（direction）
2. 根据 direction 执行 platform.move() 操作
3. 复用 OperationRecording 的平台层，跨平台自动适配

执行流程：
1. _parse_param: 解析参数
2. _get_recognition_detail: 从 argv.reco_detail.best_result.detail 提取识别结果
3. _create_platform: 创建 OperationRecording 平台实例（PlatformFactory 缓存）
4. _execute_move: 调用 platform.move() 执行移动
5. finally: platform.release_all() 确保释放按键

返回值：CustomAction.RunResult(success=True/False)

卡住检测说明：
- 不在 Action 内做卡住检测（避免 controller.post_screencap 阻塞 controller）
- 由 Pipeline 的 self-loop（next: ["AutoPathFinding"]）做隐式卡住检测：
  每次循环重新调用 PathFindingReco 识别目标位置，位置未变则继续移动。
"""

import json

from maa.context import Context
from maa.custom_action import CustomAction
from maa.define import CustomRecognitionResult


class PathFinderAction(CustomAction):
    """
    自动寻路执行器

    参数格式（JSON）：
    {
        "move_duration": 500  // 单次移动持续时间/毫秒（可选，默认 500）
    }

    字段说明：
    - move_duration: 每次 platform.move() 的持续时间

    前置依赖：
    - 前序识别器必须返回 detail.direction（str）
    - 推荐使用 PathFindingReco 作为前序识别器
    - 依赖 OperationRecording 模块的 PlatformFactory

    Pipeline 使用示例：
    {
        "PathFinderAction": {
            "custom_action": "PathFinderAction",
            "custom_action_param": {
                "move_duration": 500
            },
            "next": ["AutoPathFinding"]
        }
    }
"""

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        """
        执行寻路动作

        参数:
        - context: MaaFramework 上下文对象
        - argv: 运行参数，包含识别结果和自定义参数

        返回值:
        - CustomAction.RunResult: 执行结果
        """
        # 1. 解析参数
        param = self._parse_param(argv)

        # 2. 获取识别结果详情
        detail = self._get_recognition_detail(argv)
        if not detail:
            print("[PathFinderAction] ERROR: detail is None")
            return CustomAction.RunResult(success=False)

        direction = detail.get("direction")
        if not direction:
            print("[PathFinderAction] ERROR: direction is empty")
            return CustomAction.RunResult(success=False)

        # 3. 创建 OperationRecording 平台实例
        platform = self._create_platform(context)
        if not platform:
            return CustomAction.RunResult(success=False)

        try:
            # 4. 执行移动
            success = self._execute_move(context, platform, direction, param)
        finally:
            # 5. 确保释放所有按键（避免摇杆/方向键卡住）
            platform.release_all()

        return CustomAction.RunResult(success=success)

    def _parse_param(self, argv: CustomAction.RunArg) -> dict:
        """解析参数"""
        try:
            param = json.loads(argv.custom_action_param)
        except (json.JSONDecodeError, TypeError):
            param = {}

        return {
            "move_duration": param.get("move_duration", 500),
        }

    def _get_recognition_detail(self, argv: CustomAction.RunArg) -> dict | None:
        """获取识别结果详情"""
        reco_detail = argv.reco_detail
        if not reco_detail or not reco_detail.best_result:
            return None

        best_result = reco_detail.best_result
        if not isinstance(best_result, CustomRecognitionResult):
            # 尝试从 raw_detail 获取
            raw = getattr(reco_detail, "raw_detail", None)
            if isinstance(raw, dict) and "detail" in raw:
                detail = raw["detail"]
                if isinstance(detail, str):
                    try:
                        return json.loads(detail)
                    except (json.JSONDecodeError, TypeError):
                        return None
                elif isinstance(detail, dict):
                    return detail
            return None

        # detail 是自定义识别器返回的字典
        detail = best_result.detail
        if isinstance(detail, str):
            try:
                return json.loads(detail)
            except (json.JSONDecodeError, TypeError):
                return None
        elif isinstance(detail, dict):
            return detail

        return None

    def _create_platform(self, context: Context):
        """
        创建平台实例

        通过 OperationRecording 的 PlatformFactory 创建平台实例，
        同一 controller 复用同一 platform 实例（工厂层缓存）。

        参数:
        - context: MaaFramework 上下文

        返回值:
        - PlatformBase | None: 平台实例，失败返回 None
        """
        try:
            # 从 packages 级别导入，确保触发 @register_platform 装饰器注册
            from OperationRecording.platforms import PlatformFactory

            controller = context.tasker.controller
            return PlatformFactory.create_from_config({}, controller)
        except Exception as e:
            print(f"[PathFinderAction] ERROR creating platform: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _execute_move(
        self,
        context: Context,
        platform,
        direction: str,
        param: dict,
    ) -> bool:
        """
        执行移动操作

        参数:
        - context: MaaFramework 上下文对象（用于停止检查）
        - platform: OperationRecording 平台实例
        - direction: 移动方向（forward/backward/left/right）
        - param: 参数字典

        返回值:
        - bool: 移动成功返回 True，失败返回 False

        说明：
        单次调用 platform.move() + platform.release_all()（由 run 的 finally 保证）。
        platform.move() 由家族基类（TouchPlatform/KeyboardPlatform）提供默认实现。
        卡住检测由 Pipeline 的 self-loop 隐式完成：
        每次 AutoPathFinding 自循环都会重新调用 PathFindingReco 识别目标位置，
        位置未变化时（角色卡住）继续调用 PathFinderAction 重试。
        """
        if context.tasker.stopping:
            return False

        move_duration = param["move_duration"] / 1000.0  # 转换为秒
        return platform.move(direction, move_duration)
