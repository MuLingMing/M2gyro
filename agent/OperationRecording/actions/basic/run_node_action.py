# -*- coding: utf-8 -*-
"""
执行节点动作，具有以下功能：
1. 根据节点名称执行对应的 Pipeline 节点
2. 支持阻塞模式（等待节点执行完成）
3. 支持停止响应
"""

from typing import Dict, Any
from ..base import ActionBase
from .. import register_action


@register_action("run_node")
class RunNodeAction(ActionBase):
    """
    执行节点动作

    功能说明：
    1. 节点执行
       - 根据 node 参数执行对应的 Pipeline 节点
       - 支持阻塞模式等待节点执行完成

    2. 停止响应
       - 执行过程中检查 context.tasker.stopping
       - 收到停止通知时提前返回

    参数格式：
    {
        "action": "run_node",
        "params": {
            "node": "node_name",
            "blocking": true
        }
    }

    或无参数（不推荐）：
    {
        "action": "run_node"
    }

    字段说明：
    - node: 节点名称，必填
      - 指定要执行的 Pipeline 节点名称
    - blocking: 是否阻塞等待节点执行完成，默认 True
      - True: 等待节点执行完成后再继续
      - False: 立即返回，不等待
    """

    @property
    def name(self) -> str:
        """
        动作名称

        返回值：
        - str: "run_node"
        """
        return "run_node"

    def execute(self, params: Dict[str, Any]) -> bool:
        """
        执行动作

        参数：
        - params: 动作参数，包含 node 和 blocking

        返回值：
        - bool: 是否成功

        执行流程：
        1. 获取节点名称（必填）
        2. 获取阻塞模式（默认 False）
        3. 检查停止状态
        4. 执行节点
        5. 如果是阻塞模式，等待节点执行完成
        """
        node_name = params.get("node", "")
        if not node_name:
            return False

        blocking = params.get("blocking", False)

        if self._context is None:
            return False

        if getattr(self._context.tasker, "stopping", False):
            return False

        try:
            result = self._context.run_recognition(node_name, image=self._context.tasker.controller.post_screencap().wait().get())
            
            if result and result.hit:
                self._context.run_task(node_name)

            return True
        except Exception:
            return False
        