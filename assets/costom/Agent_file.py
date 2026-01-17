"""
Agent调试启动器
该文件的作用为：
将自定义的Agent功能注册到Agent服务器中，便于在调试时使用
"""

from maa.agent.agent_server import AgentServer

from action.Count import Count
from action.ScreenShot import ScreenShot,CheckResolution
from action.Node import DisableNode,NodeOverride



@AgentServer.custom_action("Count")
class Agent_Count(Count):
    pass


@AgentServer.custom_action("DisableNode")
class Agent_DisableNode(DisableNode):
    pass

@AgentServer.custom_action("NodeOverride")
class Agent_DisableNode(NodeOverride):
    pass


@AgentServer.custom_action("ScreenShot")
class Agent_ScreenShot(ScreenShot):
    pass

@AgentServer.custom_action("CheckResolution")
class Agent_CheckResolution(CheckResolution):
    pass