# -*- coding: utf-8 -*-
"""
条件分支动作器

功能说明：
1. 根据前序识别结果的自定义 detail.hit 字段分支执行
   - hit=True  → 执行 true 分支
   - hit=False → 执行 false 分支
2. 分支项支持两种执行模式：
   - 字符串 → context.run_task() 执行 Pipeline 节点
   - 字典   → context.run_action_direct() 直接执行操作
3. 每个分支可携带独立的 next 节点列表，分支执行完毕后依次执行

与 CovertStage 识别器配合使用：
- 类型1（命中关卡，box=关卡坐标，hit=True）→ true 分支
- 类型2（页面正确但无命中，box=[0,0,0,0]，hit=False）→ false 分支
- 类型3（未识别到页面，box=None）→ 节点未命中，Pipeline 重试/走 exceeded_next，
  IfElse 不会被执行
"""

import dataclasses
import json
from typing import Any, Dict, List, Optional, Tuple, Union

from maa.context import Context
from maa.custom_action import CustomAction
from maa.define import CustomRecognitionResult, Rect
from maa.pipeline import (
    JActionType,
    JActionParam,
    JClick,
    JClickKey,
    JCommand,
    JDoNothing,
    JInputText,
    JKey,
    JLongPress,
    JLongPressKey,
    JMultiSwipe,
    JScroll,
    JScreencap,
    JShell,
    JStartApp,
    JStopApp,
    JStopTask,
    JSwipe,
    JTouch,
    JTouchUp,
    JCustomAction,
)
from utils.logger import logger

_ACTION_PARAM_MAP: Dict[str, type] = {
    "DoNothing": JDoNothing,
    "Click": JClick,
    "LongPress": JLongPress,
    "Swipe": JSwipe,
    "MultiSwipe": JMultiSwipe,
    "TouchDown": JTouch,
    "TouchMove": JTouch,
    "TouchUp": JTouchUp,
    "ClickKey": JClickKey,
    "LongPressKey": JLongPressKey,
    "KeyDown": JKey,
    "KeyUp": JKey,
    "InputText": JInputText,
    "StartApp": JStartApp,
    "StopApp": JStopApp,
    "StopTask": JStopTask,
    "Scroll": JScroll,
    "Command": JCommand,
    "Shell": JShell,
    "Screencap": JScreencap,
    "Custom": JCustomAction,
}

BranchItem = Union[str, Dict[str, Any]]


class IfElse(CustomAction):
    """
    条件分支动作器

    根据前序识别结果的自定义 detail.hit 字段分支执行：
    - hit=True  → 执行 true 分支
    - hit=False → 执行 false 分支

    分支项支持两种执行模式：
    1. 字符串 → context.run_task() 执行 Pipeline 节点
    2. 字典   → context.run_action_direct() 直接执行操作

    分支格式（两种，向后兼容）：
    - 列表格式（无 next）：[item1, item2, ...]
    - 对象格式（带 next）：{"items": [item1, ...], "next": ["NodeA", ...]}

    参数格式：
    {
        "true": {
            "items": [{"action": "Click", "param": {"target": true}}],
            "next": ["NextStep1"]
        },
        "false": {
            "items": ["HandleNoMatch"],
            "next": ["NextStep2"]
        }
    }

    或简写格式（无 next，向后兼容）：
    {
        "true": [{"action": "Click", "param": {"target": true}}],
        "false": ["HandleNoMatch"]
    }

    字段说明：
    - true: hit=True 时执行的分支，可省略
      - 列表格式: 分支项列表，无 next
      - 对象格式:
        - items: 分支项列表
          - 字符串项: Pipeline 节点名，通过 context.run_task() 执行
          - 字典项: {"action": "操作类型", "param": {操作参数}}
            - action: JActionType 枚举值（Click/Swipe/ClickKey/Custom 等）
            - param: 对应操作类型的参数字典，与 Pipeline JSON 中 action 参数格式一致
        - next: 分支执行完毕后依次执行的 Pipeline 节点列表，可省略
    - false: hit=False 时执行的分支，格式同 true，可省略

    hit 判定逻辑：
    - Custom Recognition: 从 best_result.detail 解析 hit 字段
    - 内置 Recognition: 使用 reco_detail.hit

    Pipeline 使用示例：
    {
        "CovertStage_Select": {
            "recognition": "CovertStage",
            "action": "Custom",
            "custom_action": "IfElse",
            "custom_action_param": {
                "true": {
                    "items": [{"action": "Click", "param": {"target": true}}],
                    "next": ["CovertStage_Confirm"]
                },
                "false": {
                    "items": ["CovertStage_NoMatch"],
                    "next": ["CovertStage_Retry"]
                }
            }
        }
    }
    """

    def run(
        self, context: Context, argv: CustomAction.RunArg
    ) -> CustomAction.RunResult:
        """
        执行条件分支逻辑

        参数:
        - context: MaaFramework 上下文对象
        - argv: 运行参数，包含识别结果和自定义参数

        返回值:
        - CustomAction.RunResult: 始终返回 success=True

        执行流程:
        1. 解析 custom_action_param 获取 true/false 分支配置
        2. 从 argv.reco_detail 提取 hit 值
        3. 根据 hit 选择对应分支
        4. 解析分支格式（列表或对象），提取 items 和 next
        5. 遍历 items，依次执行
        6. 执行分支的 next 节点列表
        7. 执行中检查 stopping 信号
        """
        try:
            params: Dict[str, Any] = json.loads(argv.custom_action_param)
        except json.JSONDecodeError as e:
            logger.error(f"IfElse: 参数解析失败: {e}")
            return CustomAction.RunResult(success=True)

        true_raw = params.get("true", [])
        false_raw = params.get("false", [])

        hit = self._extract_hit(argv)

        branch_raw = true_raw if hit else false_raw
        items, next_nodes = self._parse_branch(branch_raw)

        if not items and not next_nodes:
            return CustomAction.RunResult(success=True)

        for item in items:
            if context.tasker.stopping:
                return CustomAction.RunResult(success=True)

            if isinstance(item, str):
                self._run_task(context, item)
            elif isinstance(item, dict):
                self._execute_action(context, item, argv.box)
            else:
                logger.warning(f"IfElse: 忽略无效分支项类型 {type(item)}")

        for node_name in next_nodes:
            if context.tasker.stopping:
                return CustomAction.RunResult(success=True)

            self._run_task(context, node_name)

        return CustomAction.RunResult(success=True)

    @staticmethod
    def _parse_branch(
        branch_raw: Union[List[BranchItem], Dict[str, Any]],
    ) -> Tuple[List[BranchItem], List[str]]:
        """
        解析分支配置，提取 items 和 next

        支持两种格式：
        - 列表格式：[item1, item2, ...] → items=列表本身, next=[]
        - 对象格式：{"items": [...], "next": [...]} → 按字段提取

        参数:
        - branch_raw: 原始分支配置

        返回值:
        - Tuple[items, next_nodes]:
            items: 分支项列表
            next_nodes: next 节点名列表
        """
        if isinstance(branch_raw, list):
            return branch_raw, []

        if isinstance(branch_raw, dict):
            items = branch_raw.get("items", [])
            next_nodes = branch_raw.get("next", [])
            if isinstance(next_nodes, str):
                next_nodes = [next_nodes]
            return items, next_nodes

        logger.warning(f"IfElse: 忽略无效分支格式 {type(branch_raw)}")
        return [], []

    @staticmethod
    def _extract_hit(argv: CustomAction.RunArg) -> bool:
        """
        从识别结果中提取 hit 值

        优先级：
        1. Custom Recognition: 从 best_result.detail 解析 hit 字段
        2. 内置 Recognition: 使用 reco_detail.hit

        参数:
        - argv: 运行参数

        返回值:
        - bool: hit 值
        """
        reco_detail = argv.reco_detail
        if not reco_detail or not reco_detail.hit:
            return False

        best = reco_detail.best_result
        if isinstance(best, CustomRecognitionResult):
            detail = best.detail
            if isinstance(detail, str):
                try:
                    detail = json.loads(detail)
                except (json.JSONDecodeError, TypeError):
                    return reco_detail.hit
            if isinstance(detail, dict):
                return bool(detail.get("hit", reco_detail.hit))

        return reco_detail.hit

    @staticmethod
    def _run_task(context: Context, node_name: str) -> None:
        """
        执行 Pipeline 节点任务

        参数:
        - context: MaaFramework 上下文对象
        - node_name: Pipeline 节点名
        """
        try:
            context.run_task(node_name)
        except Exception as e:
            logger.error(f"IfElse: 执行节点 {node_name} 失败: {e}")

    @staticmethod
    def _execute_action(
        context: Context, action_def: Dict[str, Any], box: Rect
    ) -> None:
        """
        通过 run_action_direct 直接执行操作

        参数:
        - context: MaaFramework 上下文对象
        - action_def: 操作定义 {"action": "类型", "param": {参数}}
        - box: 前序识别位置，传入 run_action_direct 的 box 参数

        执行流程:
        1. 从 action_def 提取 action 类型和 param 字典
        2. 根据 action 类型构造 JActionParam dataclass
        3. 调用 context.run_action_direct()
        """
        action_type = action_def.get("action", "")
        param_dict = action_def.get("param", {})

        if not action_type:
            logger.warning("IfElse: action 字段为空，跳过")
            return

        param_cls = _ACTION_PARAM_MAP.get(action_type)
        if param_cls is None:
            logger.warning(
                f"IfElse: 未知 action 类型 '{action_type}'，"
                f"可选: {list(_ACTION_PARAM_MAP.keys())}"
            )
            return

        try:
            action_param = IfElse._create_action_param(param_cls, param_dict)
        except Exception as e:
            logger.error(f"IfElse: 构造 {action_type} 参数失败: {e}")
            return

        try:
            box_tuple = (box.x, box.y, box.w, box.h)
            context.run_action_direct(
                JActionType(action_type), action_param, box=box_tuple
            )
        except Exception as e:
            logger.error(f"IfElse: 执行 action {action_type} 失败: {e}")

    @staticmethod
    def _create_action_param(param_cls: type, param_dict: Dict[str, Any]) -> Any:
        """
        根据 param 字典构造 JActionParam dataclass 实例

        仅传入 dataclass 中定义的字段，忽略多余字段

        参数:
        - param_cls: JActionParam 的子类（如 JClick、JSwipe）
        - param_dict: 参数字典

        返回值:
        - JActionParam 实例
        """
        valid_fields = {f.name for f in dataclasses.fields(param_cls)}
        filtered = {k: v for k, v in param_dict.items() if k in valid_fields}
        return param_cls(**filtered)
