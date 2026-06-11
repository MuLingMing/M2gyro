# -*- coding: utf-8 -*-
"""
条件分支动作器

功能说明：
1. 根据前序识别结果的 detail.hit_node 字段分支执行
2. 分支项支持两种执行模式：
   - 字符串 → context.run_task() 执行 Pipeline 节点
   - 字典   → context.run_action_direct() 直接执行操作
3. 每个分支可携带独立的 next 节点列表，分支执行完毕后依次执行

与 IfElseReco 识别器配合使用：
- hit_node="if"       → 执行 if 分支
- hit_node="elif[0]"  → 执行 elif[0] 分支
- hit_node="else"     → 执行 else 分支
- box=None            → 节点未命中，Pipeline 重试/走 exceeded_next
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


class IfElseAction(CustomAction):
    """
    条件分支动作器

    根据前序识别结果的 detail.hit_node 字段分支执行

    分支项支持两种执行模式：
    1. 字符串 → context.run_task() 执行 Pipeline 节点
    2. 字典   → context.run_action_direct() 直接执行操作

    分支格式（两种）：
    - 列表格式（无 next）：[item1, item2, ...]
    - 对象格式（带 next）：{"Act_or_node": [item1, ...], "next": ["NodeA", ...]}

    参数格式：
    {
        "if": {
            "Act_or_node": [{"action": "Click", "param": {"target": true}}],
            "next": ["NextStep1"]
        },
        "elif": ["ActionB", "ActionC"],
        "else": ["ActionD"]
    }

    或简写格式（无 next）：
    {
        "if": [{"action": "Click", "param": {"target": true}}],
        "elif": ["ActionB", "ActionC"],
        "else": ["ActionD"]
    }

    字段说明：
    - if: hit_node="if" 时执行的分支，可省略
    - elif: hit_node="elif[index]" 时执行的分支，可以是列表或嵌套列表，可省略
    - else: hit_node="else" 时执行的分支，可省略

    分支格式：
    - 列表格式: 分支项列表，无 next
    - 对象格式:
      - Act_or_node: 分支项列表
        - 字符串项: Pipeline 节点名，通过 context.run_task() 执行
        - 字典项: {"action": "操作类型", "param": {操作参数}}
      - next: 分支执行完毕后依次执行的 Pipeline 节点列表，可省略

    hit_node 匹配逻辑：
    - hit_node="if" → 执行 params["if"]
    - hit_node="elif[0]" → 执行 params["elif"][0]
    - hit_node="elif[1]" → 执行 params["elif"][1]
    - hit_node="else" → 执行 params["else"]

    Pipeline 使用示例：
    {
        "ConditionCheck": {
            "recognition": "IfElseReco",
            "custom_recognition_param": {
                "entry": "Node_entry",
                "if": "RecoA",
                "elif": ["RecoB", "RecoC"],
                "else": "RecoD"
            },
            "action": "Custom",
            "custom_action": "IfElseAction",
            "custom_action_param": {
                "if": {
                    "Act_or_node": [{"action": "Click", "param": {"target": true}}],
                    "next": ["ConfirmA"]
                },
                "elif": ["ActionB", "ActionC"],
                "else": ["ActionD"]
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
        1. 解析 custom_action_param 获取 if/elif/else 分支配置
        2. 从 argv.reco_detail 提取 hit_node 值
        3. 根据 hit_node 选择对应分支
        4. 解析分支格式（列表或对象），提取 Act_or_node 和 next
        5. 遍历 Act_or_node，依次执行
        6. 执行分支的 next 节点列表
        7. 执行中检查 stopping 信号
        """
        try:
            params: Dict[str, Any] = json.loads(argv.custom_action_param)
        except json.JSONDecodeError as e:
            logger.error(f"IfElse: 参数解析失败: {e}")
            return CustomAction.RunResult(success=True)

        hit_node = self._extract_hit_node(argv)

        # 根据 hit_node 选择分支
        branch_raw = self._select_branch(params, hit_node)
        if branch_raw is None:
            logger.warning(f"IfElse: 未找到匹配的分支 hit_node={hit_node}")
            return CustomAction.RunResult(success=True)

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
    def _select_branch(params: Dict[str, Any], hit_node: str) -> Any:
        """
        根据 hit_node 选择对应的分支配置

        参数:
        - params: 完整的参数字典
        - hit_node: 识别结果中的 hit_node 值

        返回值:
        - 分支配置，未找到返回 None
        """
        if not hit_node:
            return None

        # 处理 if 分支
        if hit_node == "if":
            return params.get("if")

        # 处理 elif 分支
        if hit_node.startswith("elif[") and hit_node.endswith("]"):
            try:
                index = int(hit_node[5:-1])
                elif_branches = params.get("elif", [])
                if isinstance(elif_branches, str):
                    elif_branches = [elif_branches]
                if isinstance(elif_branches, list) and 0 <= index < len(elif_branches):
                    return elif_branches[index]
            except (ValueError, IndexError):
                pass
            return None

        # 处理 else 分支
        if hit_node == "else":
            return params.get("else")

        return None

    @staticmethod
    def _parse_branch(
        branch_raw: Union[List[BranchItem], Dict[str, Any]],
    ) -> Tuple[List[BranchItem], List[str]]:
        """
        解析分支配置，提取 Act_or_node 和 next

        支持两种格式：
        - 列表格式：[item1, item2, ...] → items=列表本身, next=[]
        - 对象格式：{"Act_or_node": [...], "next": [...]} → 按字段提取

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
            items = branch_raw.get("Act_or_node", [])
            next_nodes = branch_raw.get("next", [])
            if isinstance(next_nodes, str):
                next_nodes = [next_nodes]
            return items, next_nodes

        logger.warning(f"IfElse: 忽略无效分支格式 {type(branch_raw)}")
        return [], []

    @staticmethod
    def _extract_hit_node(argv: CustomAction.RunArg) -> str:
        """
        从识别结果中提取 hit_node 值

        参数:
        - argv: 运行参数

        返回值:
        - str: hit_node 值，未找到返回空字符串
        """
        reco_detail = argv.reco_detail
        if not reco_detail:
            return ""

        best = reco_detail.best_result
        if isinstance(best, CustomRecognitionResult):
            detail = best.detail
            if isinstance(detail, str):
                try:
                    detail = json.loads(detail)
                except (json.JSONDecodeError, TypeError):
                    return ""
            if isinstance(detail, dict):
                return detail.get("hit_node", "")

        return ""

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
            logger.error(f"IfElseAction: 执行节点 {node_name} 失败: {e}")

    @staticmethod
    def _execute_action(
        context: Context, action_def: Dict[str, Any], box: Optional[Rect]
    ) -> None:
        """
        通过 run_action_direct 直接执行操作

        参数:
        - context: MaaFramework 上下文对象
        - action_def: 操作定义 {"action": "类型", "param": {参数}}
        - box: 前序识别位置，传入 run_action_direct 的 box 参数，可能为 None
        """
        action_type = action_def.get("action", "")
        param_dict = action_def.get("param", {})

        if not action_type:
            logger.warning("IfElse: action 字段为空，跳过")
            return

        if box is None:
            logger.warning(f"IfElse: box 为 None，跳过 action '{action_type}'")
            return

        param_cls = _ACTION_PARAM_MAP.get(action_type)
        if param_cls is None:
            logger.warning(
                f"IfElse: 未知 action 类型 '{action_type}'，"
                f"可选: {list(_ACTION_PARAM_MAP.keys())}"
            )
            return

        try:
            action_param = IfElseAction._create_action_param(param_cls, param_dict)
        except Exception as e:
            logger.error(f"IfElseAction: 构造 {action_type} 参数失败: {e}")
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
