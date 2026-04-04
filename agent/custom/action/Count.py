# coding=utf-8
'''
用于在流水线中记录计数并根据计数结果分支执行不同节点
（达标走 next_node，未达标走 else_node）。
重置目标节点的count
播报当前运行次数
'''

from maa.context import Context
from maa.custom_action import CustomAction
import json
from utils.logger import logger


class Count(CustomAction):
    """
    用于在流水线中记录计数并根据计数结果分支执行不同节点
    （达标走 next_node，未达标走 else_node）。
    重置目标节点的count
    播报当前运行次数

    参数格式：
    {
        "count": 0,
        "target_count": 10,
        "next_node": ["node1", "node2"],
        "else_node": ["node3"],
        "reset_node": ["node4"],
        "logger":False
    }

    字段说明：
    - count: 当前次数
    - target_count: 目标次数
    - next_node: 达到目标次数后执行的节点. 支持多个节点，按顺序执行，可以出现重复节点，可以为空
    - else_node: 未达到目标次数时执行的节点. 支持多个节点，按顺序执行，可以出现重复节点，可以为空
    - reset_node: 将指定节点的count重置为0，支持多个节点，可以为空
    - logger：是否输出运行次数，默认False
    """
    def run(
        self, context: Context, argv: CustomAction.RunArg
    ) -> CustomAction.RunResult:


        argv_dict: dict = json.loads(argv.custom_action_param)
        # print(argv.node_name,argv_dict)
        if not argv_dict:
            return CustomAction.RunResult(success=True)

        current_count = argv_dict.get("count", 0)
        target_count = argv_dict.get("target_count", 0)
        next_node = argv_dict.get("next_node", [])
        else_node = argv_dict.get("else_node", [])
        reset_node = argv_dict.get("reset_node", [])
        logger_enable = argv_dict.get("logger", False)

        # 重设reset_node的count为0
        if reset_node:
            self._reset_nodes(context=context, nodes=reset_node, reset_count=0)

        # target_count=0时，action运行else_node
        # 使得option修改target_count逻辑相同
        if current_count < target_count or target_count == 0:
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
                    f"{argv.node_name}已达到目标次数{target_count}，执行后续节点{next_node}"
                )
            self._run_nodes(context, argv_dict.get("next_node"))

        return CustomAction.RunResult(success=True)

    def _run_nodes(self, context: Context, nodes):
        """统一处理节点执行逻辑"""
        if not nodes:
            return
        if isinstance(nodes, str):
            nodes = [nodes]
        for node in nodes:
            try:
                context.run_task(node)
            except Exception as e:
                logger.error(f"CountAction：执行节点{node}时出错: {e}")

    def _reset_nodes(self, context: Context, nodes: str | list, reset_count: int):
        """重设节点的count为reset_count"""
        if not nodes:
            return
        if isinstance(nodes, str):
            nodes = [nodes]
        for node in nodes:
            # 获取node信息
            # get_node_data返回值为node_data:{"action":{"param":{"custom_action_param"}}}
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

            # 直接修改node_custom_action_param防止漏掉或新增参数
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
        修改为每50次计数
        判断count是否需要输出print：
        - 1-9：第1次、第5次输出
        - 10-99：10、20、30…输出
        - 100-999：100、200、300…输出
        - 以此类推
        """
        if count <= 0:  # 非正整数不输出
            return False

        return count % 50 == 0 or count == 1 or count == 10
        # 计算count的数量级（科学计数法10^n）：如count=5→1，count=50→10，count=500→100
        count_str = str(count)
        magnitude = 10 ** (len(count_str) - 1)  # 当前数量级（0~9*10^n）

        # 1-9的特殊逻辑：第1次或第5次
        if magnitude == 1:
            return count == 1 or count == 5
        # 两位数及以上的通用逻辑：是当前数量级的倍数
        else:
            return count % magnitude == 0
