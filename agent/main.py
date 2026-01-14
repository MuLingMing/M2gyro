"""
Agent入口
该文件的作用为：
将自定义的Agent功能注册到Agent服务器中，便于在调试时使用
"""

import sys
from maa.agent.agent_server import AgentServer
from maa.toolkit import Toolkit

from Agent_file import *


def main():
    Toolkit.init_option("./")
    # 支持自定义socket_id，方便多实例运行
    if len(sys.argv) > 1:
        print("使用自定义socket_id: " + sys.argv[-1])
        socket_id = sys.argv[-1]
    else:
        print("使用默认socket_id: MAA_AGENT_SOCKET")
        socket_id = "MAA_AGENT_SOCKET"
    AgentServer.start_up(socket_id)
    AgentServer.join()
    AgentServer.shut_down()


if __name__ == "__main__":
    main()
