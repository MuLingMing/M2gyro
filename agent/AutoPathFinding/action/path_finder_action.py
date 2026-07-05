# -*- coding: utf-8 -*-
"""
自动寻路执行器

根据前序 PathFindingReco 返回的识别结果（direction / target.distance），执行移动操作。
复用 OperationRecording 的 PlatformFactory，自动适配 ADB/Desktop 平台。

功能说明：
1. 从 argv.reco_detail.best_result.detail 获取识别结果（direction、target）
2. 根据 direction 执行 platform.move() 操作
3. 根据 target.distance 动态计算移动时长
4. 复用 OperationRecording 的平台层，跨平台自动适配

执行流程：
1. _parse_param: 解析参数
2. _get_recognition_detail: 从 argv.reco_detail.best_result.detail 提取识别结果
3. _create_platform: 创建 OperationRecording 平台实例（PlatformFactory 缓存）
4. _execute_move: 调用 platform.move() 执行移动
5. finally: platform.release_all() 确保释放按键

返回值：CustomAction.RunResult(success=True/False)

状态检测说明：
- 到达 / 卡住等状态由 PathFindingReco 在识别阶段评估并返回 detail.state
- PathFinderAction 仅负责根据 direction 和 distance 执行移动，内部不做状态判断
"""

import json
import logging

from maa.context import Context
from maa.custom_action import CustomAction
from maa.define import CustomRecognitionResult

from .param import PathFinderParam

logger = logging.getLogger(__name__)


class PathFinderAction(CustomAction):
    """
    自动寻路执行器

    参数格式（JSON）：
    {
        "move_duration": 500,         // 默认移动时长/毫秒（可选，默认 500）
        "move_duration_far": 1500,    // 远距离移动时长/毫秒（可选，默认 1500）
        "move_duration_near": 300,    // 近距离移动时长/毫秒（可选，默认 300）
        "distance_far": 200,          // 远距离阈值/像素（可选，默认 200）
        "distance_near": 50           // 近距离阈值/像素（可选，默认 50）
    }

    字段说明：
    - move_duration: 无距离信息时的默认移动时长
    - move_duration_far: 距离 ≥ distance_far 时的移动时长
    - move_duration_near: 距离 ≤ distance_near 时的移动时长
    - distance_far: 远距离阈值
    - distance_near: 近距离阈值
    - 距离在 (distance_near, distance_far) 之间时按线性插值计算时长

    前置依赖：
    - 前序识别器必须返回 detail.direction（str）
    - 方向值为 "centered" 时表示目标已在屏幕中心死区内，不执行移动
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
            logger.error("Recognition detail is None")
            return CustomAction.RunResult(success=False)

        direction = detail.get("direction")
        if direction == "centered":
            # 目标已在屏幕中心死区内，无需移动
            return CustomAction.RunResult(success=True)
        if not direction:
            logger.error("Direction is empty in recognition detail")
            return CustomAction.RunResult(success=False)

        # 3. 提取目标距离（用于动态调整移动时长）
        target_info = detail.get("target", {})
        distance = target_info.get("distance") if isinstance(target_info, dict) else None

        # 4. 创建 OperationRecording 平台实例
        platform = self._create_platform(context)
        if not platform:
            return CustomAction.RunResult(success=False)

        try:
            # 5. 执行移动
            success = self._execute_move(context, platform, direction, param, distance)
        finally:
            # 6. 确保释放所有按键（避免摇杆/方向键卡住）
            platform.release_all()

        return CustomAction.RunResult(success=success)

    def _parse_param(self, argv: CustomAction.RunArg) -> PathFinderParam:
        """解析参数"""
        try:
            param = json.loads(argv.custom_action_param)
        except (json.JSONDecodeError, TypeError):
            param = {}

        return PathFinderParam(
            move_duration=param.get("move_duration", 500),
            move_duration_far=param.get("move_duration_far", 1500),
            move_duration_near=param.get("move_duration_near", 300),
            distance_far=param.get("distance_far", 200),
            distance_near=param.get("distance_near", 50),
        )

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
        except Exception:
            logger.exception("Failed to create OperationRecording platform")
            return None

    def _execute_move(
        self,
        context: Context,
        platform,
        direction: str,
        param: PathFinderParam,
        distance: int | None,
    ) -> bool:
        """
        执行移动操作

        参数:
        - context: MaaFramework 上下文对象（用于停止检查）
        - platform: OperationRecording 平台实例
        - direction: 移动方向（forward/backward/left/right）
        - param: 执行参数
        - distance: 目标距离（像素），可能为 None

        返回值:
        - bool: 移动成功返回 True，失败返回 False

        说明：
        单次调用 platform.move() + platform.release_all()（由 run 的 finally 保证）。
        platform.move() 由家族基类（TouchPlatform/KeyboardPlatform）提供默认实现。
        移动时长根据 distance 动态计算：距离远则时长长，距离近则时长短。
        到达 / 卡住等状态由前序 PathFindingReco 返回，Action 内不做判断。
        """
        if context.tasker.stopping:
            return False

        move_duration = self._resolve_duration(distance, param)
        return platform.move(direction, move_duration)

    def _resolve_duration(self, distance: int | None, param: PathFinderParam) -> float:
        """
        根据目标距离计算移动时长（秒）

        参数:
        - distance: 目标距离（像素），None 时使用默认时长
        - param: 执行参数

        返回值:
        - float: 移动时长（秒）
        """
        if distance is None:
            return param.move_duration / 1000.0

        far = param.distance_far
        near = param.distance_near

        if far <= near:
            # 配置异常时回退到默认时长
            return param.move_duration / 1000.0

        far_ms = param.move_duration_far
        near_ms = param.move_duration_near

        if distance >= far:
            return far_ms / 1000.0
        if distance <= near:
            return near_ms / 1000.0

        # 线性插值
        ratio = (distance - near) / (far - near)
        return (near_ms + ratio * (far_ms - near_ms)) / 1000.0
