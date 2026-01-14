"""
Agent调试启动器
该文件的作用为：
将自定义的Agent功能注册到Agent服务器中，便于在调试时使用
"""

from maa.agent.agent_server import AgentServer

from action.ScreenShot import ScreenShot
from action.Count import Count


@AgentServer.custom_action("ScreenShot")
class Agent_ScreenShot(ScreenShot):
    pass

@AgentServer.custom_action("Count")
class Agent_Count(Count):
    pass

# 这里可以添加更多自定义的Agent功能
