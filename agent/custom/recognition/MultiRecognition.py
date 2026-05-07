# -*- coding: utf-8 -*-
"""
多算法组合识别器，具有以下功能：
1. 对多个Pipeline节点执行批量识别，并将结果组合为一个统一的识别结果
   - 识别结果映射为 $0、$1、$2... 供后续表达式引用
2. 支持四种逻辑判定模式：
   - AND: 所有节点都识别成功时通过（默认）
   - OR: 任意节点识别成功时通过
   - NOT: AND 的取反，任一节点未识别成功时通过
   - CUSTOM: 自定义布尔表达式判定，支持 AND/OR/NOT 和括号分组
3. 支持基于识别结果的ROI计算
   - UNION: 两个区域的并集（最小包围矩形）
   - INTERSECTION: 两个区域的交集
   - OFFSET: 区域偏移调整
   - 支持嵌套调用，如 UNION($0, OFFSET($1, 10, 10, -20, -20))
4. 支持通过 {NodeName} 引用其他已执行节点的识别结果
"""

import json
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Union

from maa.context import Context
from maa.custom_recognition import CustomRecognition
from utils.logger import logger

_PATTERN_EXTERNAL = re.compile(r"\{([^}]+)\}")
_PATTERN_FUNC = re.compile(r"(\w+)\(([^()]*)\)")
_PATTERN_TOKEN = re.compile(r"\$?\d+|[A-Za-z]+|[()]|[^$\w\s()]")


class MultiRecognition(CustomRecognition):
    """
    多算法组合识别器

    注册方式：通过 agent/custom.json 动态注册，不引入装饰器

    功能说明：
    1. 批量节点识别
       - 对 nodes 列表中的每个节点执行识别
       - 识别结果映射为 $0、$1、$2... 供后续表达式引用

    2. 逻辑判定
       - AND: 所有节点都识别成功时通过（默认）
       - OR: 任意节点识别成功时通过
       - NOT: AND 的取反，任一节点未识别成功时通过
       - CUSTOM: 使用自定义布尔表达式判定，支持 AND/OR/NOT 和括号分组

    3. ROI 计算
       - 支持固定坐标 int[4] 直接返回
       - 支持表达式计算：UNION（并集）、INTERSECTION（交集）、OFFSET（偏移）
       - 支持嵌套调用，如 UNION($0, OFFSET($1, 10, 10, -20, -20))

    4. 外部节点引用
       - 通过 {NodeName} 引用其他已执行节点的识别结果和ROI

    参数格式：
    {
        "nodes": ["节点A", "节点B", "节点C"],
        "logic": {
            "type": "CUSTOM",
            "expression": "$0 AND ($1 OR $2)"
        },
        "return": "UNION($0, $1)"
    }

    示例（涵盖所有逻辑类型和ROI计算方式）：

    1. AND逻辑 + 固定坐标：
    {
        "nodes": ["敌人A", "敌人B"],
        "logic": {"type": "AND"},
        "return": [100, 200, 300, 400]
    }

    2. OR逻辑 + 单变量引用：
    {
        "nodes": ["弹窗确认", "弹窗取消"],
        "logic": {"type": "OR"},
        "return": "$0"
    }

    3. NOT逻辑 + OFFSET偏移：
    {
        "nodes": ["加载画面"],
        "logic": {"type": "NOT"},
        "return": "OFFSET({主界面}, 50, 50, -100, -100)"
    }

    4. CUSTOM表达式 + 嵌套ROI计算：
    {
        "nodes": ["角色A", "角色B", "角色C"],
        "logic": {
            "type": "CUSTOM",
            "expression": "$0 AND ($1 OR $2)"
        },
        "return": "UNION($0, INTERSECTION($1, $2))"
    }

    5. 引用外部节点：
    {
        "nodes": ["攻击按钮"],
        "logic": {"type": "AND"},
        "return": "UNION({前置节点}, $0)"
    }

    字段说明：
    - nodes: 节点名称数组，按顺序映射为 $0、$1、$2... 用于后续表达式引用
    - logic: 逻辑判定条件
      - type: 逻辑类型
        - "AND": 所有节点都识别成功时通过（默认）
        - "OR": 任意节点识别成功时通过
        - "NOT": AND 的取反，任一节点未识别成功时通过
        - "CUSTOM": 使用自定义布尔表达式判定
      - expression: 自定义布尔表达式，仅 type="CUSTOM" 时生效
        - $0, $1, $10... 引用 nodes 数组中对应索引的节点识别结果
        - {NodeName} 引用其他已执行节点的识别结果
        - 支持 AND、OR、NOT 逻辑运算符（大小写不敏感）
        - 支持括号分组调整优先级
    - return: 返回的ROI区域
      - int[4] 格式: 直接返回固定坐标 [x, y, w, h]
      - string 格式: 基于识别结果计算的ROI表达式
        - $0, $1, $2 引用节点的识别区域
        - {NodeName} 引用其他已执行节点的识别区域
        - UNION($0, $1): 计算两个区域的并集（最小包围矩形）
        - INTERSECTION($0, $1): 计算两个区域的交集
        - OFFSET($0, dx, dy, dw, dh): 对区域进行偏移调整
        - 支持嵌套调用，如 UNION($0, OFFSET($1, 10, 10, -20, -20))

    备注：
    - 所有坐标和图片以 720p (1280x720) 为基准
    - 表达式解析不使用 eval()，防止代码注入
    """

    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> Optional[CustomRecognition.AnalyzeResult]:
        """
        执行多算法组合识别

        参数:
        - context: 上下文对象，用于执行节点识别和获取任务详情
        - argv: 分析参数，包含自定义参数JSON、当前图片、任务详情等

        返回值:
        - CustomRecognition.AnalyzeResult: 识别成功，box 为计算后的ROI
        - None: 参数错误、逻辑不满足或ROI计算失败

        执行流程:
        1. 创建会话上下文
        2. 调用核心执行逻辑（4阶段流水线）
        3. 捕获顶层异常，防止识别器崩溃
        """
        session = _SessionContext(context=context, argv=argv)
        try:
            return self._run_core(session)
        except Exception as e:
            logger.error(f"MultiRecognition执行异常: {e}")
            return None

    def _run_core(
        self, session: "_SessionContext"
    ) -> Optional[CustomRecognition.AnalyzeResult]:
        """
        核心执行逻辑，4阶段流水线

        执行流程:
        1. 解析参数: 从 JSON 中提取 nodes、logic、return 三个配置
        2. 节点识别: 对 nodes 列表中的每个节点执行识别，得到 $0、$1... 映射
        3. 逻辑判断: 根据 logic 配置判断是否满足条件
        4. ROI 计算: 根据 return 配置计算最终的 ROI 区域
        """
        try:
            params = self._parse_params(session.argv.custom_recognition_param)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"MultiRecognition参数解析失败: {e}")
            return None

        nodes, logic, return_value = params["nodes"], params["logic"], params["return"]

        try:
            node_results = self._run_nodes_recognition(session, nodes)
        except Exception as e:
            logger.error(f"MultiRecognition节点识别失败: {e}")
            return None

        try:
            if not self._check_logic_condition(session, logic, node_results):
                return None
        except Exception as e:
            logger.error(f"MultiRecognition逻辑判断失败: {e}")
            return None

        try:
            final_roi = self._process_return_value(session, return_value, node_results)
            if final_roi:
                return CustomRecognition.AnalyzeResult(box=final_roi, detail={})
            return None
        except Exception as e:
            logger.error(f"MultiRecognition ROI计算失败: {e}")
            return None

    def _parse_params(self, raw_param: str) -> Dict:
        """
        解析自定义参数JSON

        参数:
        - raw_param: JSON 字符串

        返回值:
        - dict: 包含 nodes, logic, return 三个字段

        异常:
        - ValueError: 必要字段缺失或为空
        - json.JSONDecodeError: JSON 格式错误
        """
        params = json.loads(raw_param)
        nodes = params.get("nodes", [])
        logic = params.get("logic", {"type": "AND"})
        return_value = params.get("return", None)

        if not nodes:
            raise ValueError("nodes字段不能为空或空数组")

        if return_value is None or return_value == "":
            raise ValueError("return字段不能为空")

        return {"nodes": nodes, "logic": logic, "return": return_value}

    def _run_nodes_recognition(
        self,
        session: "_SessionContext",
        nodes: List[str],
    ) -> Dict[str, Optional[List[int]]]:
        """
        对 nodes 列表中的每个节点执行识别

        参数:
        - session: 会话上下文
        - nodes: 节点名称列表

        返回值:
        - Dict[str, Optional[List[int]]]: {"$0": [x,y,w,h], "$1": None, ...}
        """
        node_results: Dict[str, Optional[List[int]]] = {}
        for i, node_name in enumerate(nodes):
            index_key = f"${i}"
            reco_detail = session.context.run_recognition(node_name, session.argv.image)

            if reco_detail and reco_detail.hit and reco_detail.box is not None:
                normalized_roi = _ROICalculator.normalize(
                    list(reco_detail.box), self._get_screen_roi(session)
                )
                node_results[index_key] = normalized_roi
            else:
                node_results[index_key] = None

        return node_results

    def _get_screen_roi(self, session: "_SessionContext") -> List[int]:
        """
        获取全屏ROI坐标（带缓存），基于720p缩放

        参数:
        - session: 会话上下文

        返回值:
        - list[int]: [0, 0, scaled_width, scaled_height]
        """
        if session.screen_roi is None:
            image = session.argv.image
            original_height, original_width = image.shape[:2]

            if original_width <= original_height:
                scaled_width = 720
                scaled_height = int(original_height * (720 / original_width))
            else:
                scaled_height = 720
                scaled_width = int(original_width * (720 / original_height))

            session.screen_roi = [0, 0, scaled_width, scaled_height]
        return session.screen_roi

    def _ensure_external_nodes_cached(
        self, session: "_SessionContext", node_names: List[str]
    ) -> None:
        """
        确保指定的外部节点识别信息已缓存，已缓存的节点不会重复查询

        参数:
        - session: 会话上下文
        - node_names: 需要查询的外部节点名称列表
        """
        uncached_set = {
            name for name in node_names if name not in session.external_node_cache
        }

        if not uncached_set:
            return

        task_detail = session.argv.task_detail
        task_id = task_detail.task_id
        task_detail_result = session.context.tasker.get_task_detail(task_id)

        if task_detail_result and task_detail_result.nodes:
            for node_detail in reversed(task_detail_result.nodes):
                if node_detail.name in uncached_set:
                    reco = node_detail.recognition
                    box = reco.box if reco is not None else None
                    recognition_success = box is not None
                    session.external_node_cache[node_detail.name] = recognition_success

                    if box is not None:
                        external_roi = _ROICalculator.normalize(
                            list(box),
                            self._get_screen_roi(session),
                        )
                        session.external_roi_cache[node_detail.name] = external_roi
                    else:
                        session.external_roi_cache[node_detail.name] = None

                    uncached_set.discard(node_detail.name)

        for remaining_node in uncached_set:
            logger.warning(f"外部节点 {remaining_node} 未找到")
            session.external_node_cache[remaining_node] = False
            session.external_roi_cache[remaining_node] = None

    def _check_logic_condition(
        self,
        session: "_SessionContext",
        logic: Dict,
        node_results: Dict[str, Optional[List[int]]],
    ) -> bool:
        """
        根据 logic 配置判断识别结果是否满足条件

        参数:
        - session: 会话上下文
        - logic: 逻辑配置字典
        - node_results: 节点识别结果映射

        返回值:
        - bool: 条件满足返回 True
        """
        logic_type = logic.get("type", "AND")

        if logic_type == "AND":
            return all(v is not None for v in node_results.values())

        elif logic_type == "OR":
            return any(v is not None for v in node_results.values())

        elif logic_type == "NOT":
            return any(v is None for v in node_results.values())

        elif logic_type == "CUSTOM":
            expression = logic.get("expression", "")
            if expression == "":
                logger.error("未提供expression")
                return False
            return self._evaluate_logic_expression(session, expression, node_results)

        else:
            logger.error(f"不支持的logic类型: {logic_type}")
            return False

    def _resolve_expression_vars(
        self,
        session: "_SessionContext",
        expression: str,
        node_results: Dict[str, Optional[List[int]]],
        value_converter: Callable[[str, bool, Optional[List[int]]], str],
    ) -> str:
        """
        统一的表达式变量替换

        参数:
        - session: 会话上下文
        - expression: 原始表达式
        - node_results: $索引 → ROI 映射
        - value_converter: 值转换函数 (key, hit, roi) -> replacement_string

        返回值:
        - str: 替换后的表达式
        """
        result = expression

        if "{" in result:
            names = sorted(
                set(_PATTERN_EXTERNAL.findall(result)), key=len, reverse=True
            )
            if names:
                self._ensure_external_nodes_cached(session, names)
                for name in names:
                    hit = session.external_node_cache[name]
                    roi = session.external_roi_cache[name]
                    result = result.replace(
                        f"{{{name}}}", value_converter(name, hit, roi)
                    )

        for key, roi in node_results.items():
            result = result.replace(key, value_converter(key, roi is not None, roi))

        return result

    def _evaluate_logic_expression(
        self,
        session: "_SessionContext",
        expression: str,
        node_results: Dict[str, Optional[List[int]]],
    ) -> bool:
        """
        计算自定义布尔逻辑表达式

        参数:
        - session: 会话上下文
        - expression: 布尔表达式字符串
        - node_results: 节点识别结果映射

        返回值:
        - bool: 表达式求值结果
        """
        try:
            eval_expression = self._resolve_expression_vars(
                session,
                expression,
                node_results,
                lambda _k, hit, _r: "True" if hit else "False",
            )

            return _BoolExpressionParser.evaluate(eval_expression)

        except Exception as e:
            logger.error(f"逻辑表达式计算失败: {expression}, 错误: {e}")
            return False

    def _process_return_value(
        self,
        session: "_SessionContext",
        return_value: Union[str, List],
        node_results: Dict[str, Optional[List[int]]],
    ) -> Optional[List[int]]:
        """
        处理 return 配置，支持固定坐标和表达式两种格式

        参数:
        - session: 会话上下文
        - return_value: int[4] 固定坐标 或 ROI表达式字符串
        - node_results: 节点识别结果映射

        返回值:
        - list[int]: 计算后的ROI坐标 [x, y, w, h]
        - None: 格式错误或计算失败
        """
        if isinstance(return_value, list) and len(return_value) == 4:
            try:
                result = [int(x) for x in return_value]
                screen_roi = self._get_screen_roi(session)
                clipped = _ROICalculator.intersection(result, screen_roi)
                if clipped[2] <= 0 or clipped[3] <= 0:
                    logger.warning(f"return固定坐标完全超出屏幕范围: {result}")
                    return None
                return clipped
            except (ValueError, TypeError):
                logger.error(f"return坐标格式错误: {return_value}")
                return None

        elif isinstance(return_value, str):
            return self._calculate_roi_expression(session, return_value, node_results)

        else:
            logger.error(f"return值类型错误，应为int[4]或string: {return_value}")
            return None

    def _calculate_roi_expression(
        self,
        session: "_SessionContext",
        expression: str,
        node_results: Dict[str, Optional[List[int]]],
    ) -> Optional[List[int]]:
        """
        计算字符串形式的ROI表达式

        参数:
        - session: 会话上下文
        - expression: ROI表达式
        - node_results: 节点识别结果映射

        返回值:
        - list[int]: 计算并裁剪到屏幕范围内的ROI [x, y, w, h]
        - None: 计算失败或结果完全超出屏幕
        """
        try:
            eval_expression = self._resolve_expression_vars(
                session,
                expression.strip(),
                node_results,
                lambda _k, _h, roi: (
                    f"[{roi[0]},{roi[1]},{roi[2]},{roi[3]}]"
                    if roi is not None
                    else "[0,0,0,0]"
                ),
            )

            result = self._evaluate_roi_functions(eval_expression)

            if result is None:
                logger.warning("ROI函数求值结果为None")
                return None
            if len(result) != 4:
                logger.error(f"ROI函数求值结果长度错误: 期望4个，得到{len(result)}")
                return None

            final_roi = [int(x) for x in result]
            screen_roi = self._get_screen_roi(session)
            clipped_roi = _ROICalculator.intersection(final_roi, screen_roi)

            if clipped_roi[2] <= 0 or clipped_roi[3] <= 0:
                logger.warning(f"ROI计算结果完全超出屏幕范围: {final_roi}")
                return None

            return clipped_roi

        except Exception as e:
            logger.error(f"ROI表达式计算失败: {expression}, 错误: {e}")
            return None

    def _evaluate_roi_functions(self, expression: str) -> Optional[List[int]]:
        """
        递归求解表达式中的ROI函数调用，直到无函数调用为止

        参数:
        - expression: 已完成变量替换的ROI表达式

        返回值:
        - list[int]: 最终的ROI坐标 [x, y, w, h]
        - None: 任何函数执行失败
        """
        while True:
            match = _PATTERN_FUNC.search(expression)
            if not match:
                break

            func_name = match.group(1)
            func_args = match.group(2)
            full_match = match.group(0)

            func_result = self._execute_roi_function(func_name, func_args)
            if func_result is None:
                return None

            result_str = (
                f"[{func_result[0]},{func_result[1]},{func_result[2]},{func_result[3]}]"
            )
            expression = expression.replace(full_match, result_str, 1)

        return _ROICalculator.parse_roi(expression)

    def _execute_roi_function(
        self, func_name: str, func_args: str
    ) -> Optional[List[int]]:
        """
        执行单个ROI函数调用

        支持的函数:
        - UNION(roi1, roi2): 两个区域的并集
        - INTERSECTION(roi1, roi2): 两个区域的交集
        - OFFSET(roi, dx, dy, dw, dh): 区域偏移调整

        参数:
        - func_name: 函数名称
        - func_args: 函数参数字符串

        返回值:
        - list[int]: 计算后的ROI坐标
        - None: 参数错误或计算失败
        """
        try:
            args = self._parse_function_args(func_args)

            if func_name in _ROICalculator._BINARY_HANDLERS:
                if len(args) != 2:
                    logger.error(
                        f"{func_name}函数需要2个参数，得到{len(args)}个: {args}"
                    )
                    return None
                roi1 = _ROICalculator.parse_roi(args[0])
                roi2 = _ROICalculator.parse_roi(args[1])
                if roi1 is None or roi2 is None:
                    logger.debug(
                        f"{func_name}参数解析失败: args={args}, roi1={roi1}, roi2={roi2}"
                    )
                    return None
                return _ROICalculator._BINARY_HANDLERS[func_name](roi1, roi2)

            elif func_name == "OFFSET":
                if len(args) != 5:
                    logger.error(f"OFFSET函数需要5个参数，得到{len(args)}个: {args}")
                    return None
                roi = _ROICalculator.parse_roi(args[0])
                if roi is None:
                    logger.debug(f"OFFSET参数解析失败: args={args}, roi={roi}")
                    return None
                try:
                    dx, dy, dw, dh = [int(x) for x in args[1:5]]
                except (ValueError, TypeError):
                    logger.error(f"OFFSET偏移参数格式错误: {args[1:5]}")
                    return None
                return _ROICalculator.offset(roi, dx, dy, dw, dh)

            else:
                logger.error(f"不支持的ROI函数: {func_name}")
                return None

        except Exception as e:
            logger.error(f"执行ROI函数失败: {func_name}({func_args}), 错误: {e}")
            return None

    @staticmethod
    def _parse_function_args(args_str: str) -> List[str]:
        """
        解析函数参数字符串，正确处理包含方括号的ROI参数

        参数:
        - args_str: 函数参数字符串，如 "[0,0,100,100],[50,50,200,200]"

        返回值:
        - list[str]: 参数列表
        """
        args = []
        current_arg = ""
        bracket_count = 0

        for char in args_str:
            if char == "[":
                bracket_count += 1
                current_arg += char
            elif char == "]":
                bracket_count -= 1
                current_arg += char
            elif char == "," and bracket_count == 0:
                args.append(current_arg.strip())
                current_arg = ""
            else:
                current_arg += char

        if current_arg:
            args.append(current_arg.strip())

        return args


@dataclass
class _SessionContext:
    """
    单次 analyze() 调用的会话上下文

    字段说明:
    - context: MaaFramework 上下文对象
    - argv: 分析参数
    - external_node_cache: 外部节点识别结果缓存 {NodeName: bool}
    - external_roi_cache: 外部节点 ROI 缓存 {NodeName: roi}
    - screen_roi: 屏幕全屏ROI缓存 [0, 0, w, h]
    """

    context: Context
    argv: CustomRecognition.AnalyzeArg
    external_node_cache: Dict[str, bool] = field(default_factory=dict)
    external_roi_cache: Dict[str, Optional[List[int]]] = field(default_factory=dict)
    screen_roi: Optional[List[int]] = None


class _BoolExpressionParser:
    """
    安全的布尔表达式解析器，防止代码注入

    - 将布尔表达式字符串解析为 token 列表
    - 使用递归下降解析器求值
    - 仅支持 True/False/AND/OR/NOT/() 六种 token
    - 优先级: NOT > AND > OR
    - 不使用 eval()，防止任意代码执行
    """

    @staticmethod
    def evaluate(expression: str) -> bool:
        """
        解析并求值布尔表达式

        参数:
        - expression: 已完成变量替换的布尔表达式，仅含 True/False/AND/OR/NOT/()

        返回值:
        - bool: 表达式求值结果
        """
        tokens = _BoolExpressionParser._tokenize(expression)
        pos = [0]
        result = _BoolExpressionParser._parse_or(tokens, pos)

        if pos[0] < len(tokens):
            raise ValueError(f"Unexpected token after expression: {tokens[pos[0]]}")

        return result

    @staticmethod
    def _parse_or(tokens: List[str], pos: List[int]) -> bool:
        """解析 OR 级别表达式: and_expr (OR and_expr)*"""
        left = _BoolExpressionParser._parse_and(tokens, pos)
        while pos[0] < len(tokens) and tokens[pos[0]] == "OR":
            pos[0] += 1
            right = _BoolExpressionParser._parse_and(tokens, pos)
            left = left or right
        return left

    @staticmethod
    def _parse_and(tokens: List[str], pos: List[int]) -> bool:
        """解析 AND 级别表达式: not_expr (AND not_expr)*"""
        left = _BoolExpressionParser._parse_not(tokens, pos)
        while pos[0] < len(tokens) and tokens[pos[0]] == "AND":
            pos[0] += 1
            right = _BoolExpressionParser._parse_not(tokens, pos)
            left = left and right
        return left

    @staticmethod
    def _parse_not(tokens: List[str], pos: List[int]) -> bool:
        """解析 NOT 级别表达式: NOT* atom"""
        if pos[0] < len(tokens) and tokens[pos[0]] == "NOT":
            pos[0] += 1
            return not _BoolExpressionParser._parse_not(tokens, pos)
        return _BoolExpressionParser._parse_atom(tokens, pos)

    @staticmethod
    def _parse_atom(tokens: List[str], pos: List[int]) -> bool:
        """
        解析原子表达式: TRUE / FALSE / ( or_expr )

        异常:
        - ValueError: 遇到未知 token 或缺少右括号
        """
        if pos[0] >= len(tokens):
            raise ValueError("Unexpected end of expression")

        token = tokens[pos[0]]

        if token == "(":
            pos[0] += 1
            result = _BoolExpressionParser._parse_or(tokens, pos)
            if pos[0] < len(tokens) and tokens[pos[0]] == ")":
                pos[0] += 1
            else:
                raise ValueError("Missing closing parenthesis")
            return result

        pos[0] += 1
        if token == "TRUE":
            return True
        if token == "FALSE":
            return False

        raise ValueError(f"Unexpected token: {token}")

    @staticmethod
    def _tokenize(expression: str) -> List[str]:
        """
        将布尔表达式字符串分词为 token 列表，并统一转为大写

        参数:
        - expression: 布尔表达式字符串

        返回值:
        - list[str]: token 列表（已大写化）
        """
        tokens = _PATTERN_TOKEN.findall(expression)
        return [t.upper() for t in tokens if t.strip()]


class _ROICalculator:
    """
    ROI 区域几何运算工具类

    功能:
    1. 并集: union — 两个区域的最小包围矩形
    2. 交集: intersection — 两个区域的重叠区域
    3. 偏移: offset — 对区域进行平移和缩放
    4. 标准化: normalize — 将全屏标记转换为实际屏幕坐标
    5. 解析: parse_roi — 将 "[x,y,w,h]" 解析为坐标列表
    6. 分发: _BINARY_HANDLERS 字典快速查找并集/交集计算函数
    """

    _BINARY_HANDLERS: Dict[str, Callable[[List[int], List[int]], List[int]]] = {}

    @staticmethod
    def union(roi1: List[int], roi2: List[int]) -> List[int]:
        """
        计算两个ROI区域的并集（最小包围矩形）

        参数:
        - roi1: 第一个ROI [x, y, w, h]
        - roi2: 第二个ROI [x, y, w, h]

        返回值:
        - list[int]: 包含两个区域的最小包围矩形 [x, y, w, h]
        """
        x1, y1, w1, h1 = roi1
        x2, y2, w2, h2 = roi2

        if w1 <= 0 and h1 <= 0:
            return roi2
        if w2 <= 0 and h2 <= 0:
            return roi1

        left = min(x1, x2)
        top = min(y1, y2)
        right = max(x1 + w1, x2 + w2)
        bottom = max(y1 + h1, y2 + h2)

        return [left, top, right - left, bottom - top]

    @staticmethod
    def intersection(roi1: List[int], roi2: List[int]) -> List[int]:
        """
        计算两个ROI区域的交集

        参数:
        - roi1: 第一个ROI [x, y, w, h]
        - roi2: 第二个ROI [x, y, w, h]

        返回值:
        - list[int]: 交集区域 [x, y, w, h]，无交集时返回 [0, 0, 0, 0]
        """
        x1, y1, w1, h1 = roi1
        x2, y2, w2, h2 = roi2

        if w1 <= 0 or h1 <= 0:
            return [0, 0, 0, 0]
        if w2 <= 0 or h2 <= 0:
            return [0, 0, 0, 0]

        left = max(x1, x2)
        top = max(y1, y2)
        right = min(x1 + w1, x2 + w2)
        bottom = min(y1 + h1, y2 + h2)

        if left >= right or top >= bottom:
            return [0, 0, 0, 0]

        return [left, top, right - left, bottom - top]

    @staticmethod
    def offset(roi: List[int], dx: int, dy: int, dw: int, dh: int) -> List[int]:
        """
        对ROI区域进行偏移调整

        参数:
        - roi: 原始ROI [x, y, w, h]
        - dx: x轴偏移量
        - dy: y轴偏移量
        - dw: 宽度调整量
        - dh: 高度调整量

        返回值:
        - list[int]: 偏移后的ROI [x+dx, y+dy, w+dw, h+dh]
        """
        x, y, w, h = roi
        return [x + dx, y + dy, w + dw, h + dh]

    @staticmethod
    def normalize(roi: List[int], screen_roi: List[int]) -> List[int]:
        """
        标准化ROI坐标，将 [0,0,0,0]（全屏标记）转换为实际屏幕坐标

        参数:
        - roi: 原始ROI坐标
        - screen_roi: 实际屏幕坐标 [x, y, w, h]

        返回值:
        - list[int]: 标准化后的ROI坐标
        """
        if roi == [0, 0, 0, 0]:
            return screen_roi
        return roi

    @staticmethod
    def parse_roi(expression: str) -> Optional[List[int]]:
        """
        解析ROI坐标字符串为坐标列表

        参数:
        - expression: ROI坐标字符串，格式为 "[x,y,w,h]"

        返回值:
        - list[int]: ROI坐标 [x, y, w, h]
        - None: 格式无效或解析失败
        """
        try:
            if expression.startswith("[") and expression.endswith("]"):
                coords = expression[1:-1].split(",")
                if len(coords) != 4:
                    return None
                return [int(x.strip()) for x in coords]
            return None
        except (ValueError, TypeError):
            return None


_ROICalculator._BINARY_HANDLERS = {
    "UNION": _ROICalculator.union,
    "INTERSECTION": _ROICalculator.intersection,
}
