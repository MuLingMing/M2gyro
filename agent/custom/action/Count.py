# -*- coding: utf-8 -*-
"""
计数执行action，具有以下功能：
1. 在流水线中记录计数并根据计数结果分支执行不同节点
   - 达标走 next_node
   - 未达标走 else_node
2. 重置目标节点的count
3. 播报当前运行次数

功能说明：
1. 计数管理
    - 记录当前运行次数
    - 达到目标次数后执行 next_node
    - 未达到目标次数时执行 else_node

2. 节点重置
    - 可将指定节点的 count 重置为 0

3. 运行播报
    - 可配置是否输出运行次数
"""

from maa.context import Context
from maa.custom_action import CustomAction
import json
from utils.logger import logger
from param_merger import ParamMerger


class Count(CustomAction):
    """
    计数执行动作器

    参数格式：
    {
        "count": 0,
        "target_count": 10,
        "next_node": ["node1", "node2"],
        "else_node": ["node3"],
        "reset_node": ["node4"],
        "logger_count": False,
        "log_else": "当前运行次数为{count}, 目标次数为{target_count}",
        "log_next": "{node_name}已达到目标次数{target_count}"
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
    - logger_count: 是否输出运行次数或按倍数输出运行次数，默认 False
      - False: 不输出运行次数
      - True: 不输出运行次数到达目标次数前的次数，仅输出达到目标次数时的次数
      - 正整数: 每 logger_count 次输出一次
    - log_else: 未达标时的自定义日志模板，支持占位符
      - 可用占位符：{count}, {target_count}, {node_name}, {next_node}, {else_node}
      - 在 logger_count 为任意非 False 值时且 log_else 为 True 时，生效
    - log_next: 已达标时的自定义日志模板，支持占位符
      - 可用占位符：{count}, {target_count}, {node_name}, {next_node}, {else_node}
      - 在 logger_count 为任意非 False 值时且 log_next 为 True 时，生效

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
        if reco_datail := argv.reco_detail:
            if hit := reco_datail.hit:
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
                    "logger_count": (bool, int),
                    "log_else": str,
                    "log_next": str,
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
        logger_count = params.get("logger_count", False)
        log_else = params.get("log_else", "")
        log_next = params.get("log_next", "")

        # 重设reset_node的count为0
        if reset_node:
            self._reset_nodes(context=context, nodes=reset_node, reset_count=0)

        # target_count=0时，action运行else_node
        # 使得option修改target_count逻辑相同
        if current_count < target_count - 1 or target_count == 0:
            current_count = current_count + 1
            self._reset_nodes(
                context=context, nodes=argv.node_name, reset_count=current_count
            )

            # 运行播报
            if logger_count:
                # 检查是否达到输出倍数
                if self._magnitude(count=current_count, logger_count=logger_count):
                    if log_else:
                        # 使用自定义模板格式化输出
                        message = self._format_log_message(
                            log_else,
                            current_count,
                            target_count,
                            argv.node_name,
                            next_node,
                            else_node,
                        )
                        logger.info(message)
                    elif target_count == 0:
                        logger.info(
                            f'"{argv.node_name}"当前运行次数为{current_count}, 无限循环中...'
                        )
                    else:
                        logger.info(
                            f'"{argv.node_name}"当前运行次数为{current_count}, 目标次数为{target_count}'
                        )

            self._run_nodes(context, else_node)

        else:
            self._reset_nodes(context=context, nodes=argv.node_name, reset_count=0)

            # 运行播报
            if logger_count:
                if log_next:
                    # 达标时使用自定义模板
                    message = self._format_log_message(
                        log_next,
                        current_count,
                        target_count,
                        argv.node_name,
                        next_node,
                        else_node,
                    )
                    logger.info(message)
                else:
                    logger.info(f'"{argv.node_name}"已达到目标次数{target_count}')
            self._run_nodes(context, next_node)

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

    def _format_log_message(
        self,
        log_message: str,
        count: int,
        target_count: int,
        node_name: str,
        next_node: list,
        else_node: list,
    ) -> str:
        """
        格式化自定义日志消息

        参数:
        - log_message: 日志模板字符串
        - count: 当前计数
        - target_count: 目标计数
        - node_name: 当前节点名称
        - next_node: 达标后执行的节点列表
        - else_node: 未达标时执行的节点列表

        返回值:
        - str: 格式化后的消息字符串

        可用占位符:
        - {count}: 当前运行次数
        - {target_count}: 目标次数
        - {node_name}: 当前节点名称
        - {next_node}: 达标后执行的节点
        - {else_node}: 未达标时执行的节点
        """
        try:
            return log_message.format(
                count=count,
                target_count=target_count,
                node_name=node_name,
                next_node=next_node,
                else_node=else_node,
            )
        except (KeyError, ValueError, IndexError) as e:
            logger.warning(f"Count: 日志模板格式化失败: {e}，使用原始消息")
            return log_message

    def _magnitude(self, count: int, logger_count: int | bool = False) -> bool:
        """
        判断是否需要输出运行次数

        参数:
        - count: 当前计数
        - logger_count: 输出频率控制参数
          - False/True: 不输出
          - 正整数: 每 logger_count 次输出一次（含第 1 次和第 logger_count 次）
          - 非正整数或其他类型: 使用默认行为（每 10 次输出一次）

        返回值:
        - bool: 是否需要输出
        """
        if count <= 0:
            return False
        if logger_count is False or logger_count is True:
            return False  # False/True 都不输出（True 的输出由 log_next 处理）
        if not isinstance(logger_count, int) or logger_count <= 0:
            return count % 10 == 0 or count == 1 or count == 10
        return count % logger_count == 0 or count == 1 or count == logger_count
