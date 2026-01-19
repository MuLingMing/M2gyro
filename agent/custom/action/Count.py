# coding=utf-8
'''
提供一个自定义动作类 Count（继承自 CustomAction）
用于在流水线中记录计数并根据计数结果分支执行不同节点
（达标走 next_node，未达标走 else_node）。

'''
'''
使用示例：
"action": {
    "type": "Count",
    "param": {
        "custom_action_param": {
            "count": 0,
            "target_count": 10,
            "next_node": ["node1", "node2"],
            "else_node": ["node3"]
        }
    }
}
结果：
- 每次执行 Count 动作时，count 会自增 1。
- 当 count 超过 target_count 时，执行 next_node 列表中的节点。
- 否则，执行 else_node 列表中的节点。
'''


from maa.context import Context
from maa.custom_action import CustomAction
import json


class Count(CustomAction):
    '''
    动作主入口。
    读取 argv.custom_action_param（JSON）
    根据 count 与 target_count 决定走哪一组后续节点（next_node 或 else_node）
    并把更新后的状态写回流水线。
    '''
    def run(
        self, context: Context, argv: CustomAction.RunArg
    ) -> CustomAction.RunResult:
        """
        自定义动作：
        custom_action_param:
            {
                "count": 0,
                "target_count": 10,
                "next_node": ["node1", "node2"],
                "else_node": ["node3"],
            }
        count: 当前次数
        target_count: 目标次数
        next_node: 达到目标次数后执行的节点. 支持多个节点，按顺序执行，可以出现重复节点，可以为空
        else_node: 未达到目标次数时执行的节点. 支持多个节点，按顺序执行，可以出现重复节点，可以为空
        """

        argv_dict: dict = json.loads(argv.custom_action_param)
        print(argv_dict)
        if not argv_dict:
            return CustomAction.RunResult(success=True)

        current_count = argv_dict.get("count", 0)
        target_count = argv_dict.get("target_count", 0)
        next_node=argv_dict.get("next_node",[])
        else_node=argv_dict.get("else_node",[])


        if current_count < target_count:
            argv_dict["count"] = current_count + 1
            context.override_pipeline(
                {argv.node_name: {"custom_action_param": argv_dict}}
            )
            print(f"当前运行次数为{argv_dict['count']}, 目标次数为{target_count}")
            self._run_nodes(context, else_node)
        else:
            context.override_pipeline(
                {
                    argv.node_name: {
                        "custom_action_param": {
                            "count": 0,
                            "target_count": target_count,
                            "else_node": else_node,
                            "next_node": next_node,
                        }
                    }
                }
            )
            print(f"已达到目标次数{target_count}，执行后续节点")
            self._run_nodes(context, argv_dict.get("next_node"))

        return CustomAction.RunResult(success=True)

    def _run_nodes(self, context: Context, nodes):
        """统一处理节点执行逻辑"""
        if not nodes:
            return
        if isinstance(nodes, str):
            nodes = [nodes]
        for node in nodes:
            context.run_task(node)