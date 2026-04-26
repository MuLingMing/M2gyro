# -*- coding: utf-8 -*-
"""
计数执行action，具有以下功能：
1. 在流水线中记录计数并根据计数结果分支执行不同节点
   - 达标走 next_node
   - 未达标走 else_node
2. 重置目标节点的count
3. 播报当前运行次数
"""

from maa.context import Context
from maa.custom_action import CustomAction
import json
from utils.logger import logger
from param_merger import ParamMerger


class Count(CustomAction):
    """
    计数执行动作器

    功能说明：
    1. 计数管理
       - 记录当前运行次数
       - 达到目标次数后执行 next_node
       - 未达到目标次数时执行 else_node

    2. 节点重置
       - 可将指定节点的 count 重置为 0

    3. 运行播报
       - 可配置是否输出运行次数

    参数格式：
    {
        "count": 0,
        "target_count": 10,
        "next_node": ["node1", "node2"],
        "else_node": ["node3"],
        "reset_node": ["node4"],
        "logger": False
    }

    字段说明：
    - count: 当前次数，默认 0
    - target_count: 目标次数，默认 0
    - next_node: 达到目标次数后执行的节点
      - 支持多个节点，按顺序执行
      - 可以出现重复节点
      - 可以为空
    - else_node: 未达到目标次数时执行的节点
      - 支持多个节点，按顺序执行
      - 可以出现重复节点
      - 可以为空
    - reset_node: 将指定节点的 count 重置为 0
      - 支持多个节点
      - 可以为空
    - logger: 是否输出运行次数，默认 False

    备注：
    - target_count=0 时，始终执行 else_node
    - 每次执行后会自动更新当前节点的 count 值
    """

    def run(
        self, context: Context, argv: CustomAction.RunArg
    ) -> CustomAction.RunResult:
        """
        执行计数逻辑

        参数:
        - context: 上下文对象，用于执行节点任务和获取节点数据
        - argv: 运行参数，包含节点名称和自定义参数

        返回值:
        - CustomAction.RunResult: 执行结果
        - 执行成功: success=True

        执行流程:
        1. 解析参数
        2. 重置指定节点的 count
        3. 判断当前计数是否达到目标次数
        4. 根据判断结果执行相应节点
        5. 更新当前节点的 count 值
        """

        # 未命中任何节点，直接返回成功
        if reco_datail :=argv.reco_detail:
            if hit:=reco_datail.hit:
                if not hit:
                    return CustomAction.RunResult(success=True)
        
        # 解析参数
        try:
            custom_action_param: dict = json.loads(argv.custom_action_param)
        except json.JSONDecodeError as e:
            logger.error(f"Count: 参数解析失败: {e}")
            return CustomAction.RunResult(success=True)
        if node_data := context.get_node_data(argv.node_name):
            attach_params = node_data.get("attach", {})
        else:
            attach_params = {}
        # 获取合并后的参数字典
        if not custom_action_param:
            return CustomAction.RunResult(success=True)
        else:
            if not attach_params:
                params = custom_action_param
            else:
                schema = {
                    "count": int,
                    "target_count": int,
                    "next_node": (str, list),
                    "else_node": (str, list),
                    "reset_node": (str, list),
                    "logger": bool,
                }
                
                params = ParamMerger.merge(
                    "action", custom_action_param, attach_params, schema
                )
        if not params:
            return CustomAction.RunResult(success=True)
        
        current_count = params.get("count", 0)
        target_count = params.get("target_count", 0)
        next_node = params.get("next_node", [])
        else_node = params.get("else_node", [])
        reset_node = params.get("reset_node", [])
        logger_enable = params.get("logger", False)

        # 重设reset_node的count为0
        if reset_node:
            self._reset_nodes(context=context, nodes=reset_node, reset_count=0)

        # target_count=0时，action运行else_node
        # 使得option修改target_count逻辑相同
        if current_count < target_count-1 or target_count == 0:
            current_count = current_count + 1
            self._reset_nodes(
                context=context, nodes=argv.node_name, reset_count=current_count
            )

            # 运行播报
            if logger_enable:
                if self._magnitude(current_count):
                    if target_count == 0:
                        logger.info(f"当前运行次数为{current_count}, 无限循环中...")
                    else:
                        logger.info(
                            f"当前运行次数为{current_count}, 目标次数为{target_count}"
                        )

            self._run_nodes(context, else_node)

        else:
            self._reset_nodes(context=context, nodes=argv.node_name, reset_count=0)

            # 运行播报
            if logger_enable:
                logger.info(
                    f"{argv.node_name}已达到目标次数{target_count}"
                )
            self._run_nodes(context, params["next_node"])

        return CustomAction.RunResult(success=True)

    def _run_nodes(self, context: Context, nodes):
        """
        统一处理节点执行逻辑

        参数:
        - context: 上下文对象，用于执行节点任务
        - nodes: 节点列表或单个节点名称
        """
        if not nodes:
            return
        if isinstance(nodes, str):
            nodes = [nodes]
        for node in nodes:
            try:
                context.run_task(node)
            except Exception as e:
                logger.error(f"Count: 执行节点 {node} 失败: {e}")

    def _reset_nodes(self, context: Context, nodes: str | list, reset_count: int):
        """
        重设节点的 count 为 reset_count

        参数:
        - context: 上下文对象，用于获取和修改节点数据
        - nodes: 节点列表或单个节点名称
        - reset_count: 要重置的计数
        """
        if not nodes:
            return
        if isinstance(nodes, str):
            nodes = [nodes]
        for node in nodes:
            # 获取节点信息
            # get_node_data 返回值为 node_data: {"action": {"param": {"custom_action_param"}}}
            node_data = context.get_node_data(node)
            if not node_data:
                return
            node_action_param = node_data.get("action", {}).get("param", {})
            if (
                not node_action_param.get("custom_action", "")
            ) or node_action_param.get("custom_action", "") != "Count":
                return

            node_custom_action_param = node_action_param.get("custom_action_param", {})
            if not node_custom_action_param:
                return

            # 直接修改 node_custom_action_param 防止漏掉或新增参数
            node_custom_action_param["count"] = reset_count

            context.override_pipeline(
                {node: {"custom_action_param": node_custom_action_param}}
            )

            # if reset_count == 0:
            #     print(f'"{node}"节点已重置count为{reset_count}！')
            # node_custom_action_param_check = (
            #     context.get_node_data(node)
            #     .get("action", {})
            #     .get("param", {})
            #     .get("custom_action_param", {})
            # )
            # print(f"重设节点{node}内容检查为{node_custom_action_param_check}")

    def _magnitude(self, count: int) -> bool:
        """
        判断是否需要输出运行次数

        参数:
        - count: 当前计数

        返回值:
        - bool: 是否需要输出

        输出规则:
        - 每 50 次计数输出一次
        - 第 1 次和第 10 次也会输出
        """
        if count <= 0:  # 非正整数不输出
            return False
        return count % 50 == 0 or count == 1 or count == 10

        # # 计算count的数量级（科学计数法10^n）：如count=5→1，count=50→10，count=500→100
        # count_str = str(count)
        # magnitude = 10 ** (len(count_str) - 1)  # 当前数量级（0~9*10^n）

        # # 1-9的特殊逻辑：第1次或第5次
        # if magnitude == 1:
        #     return count == 1 or count == 5
        # # 两位数及以上的通用逻辑：是当前数量级的倍数
        # else:
        #     return count % magnitude == 0
