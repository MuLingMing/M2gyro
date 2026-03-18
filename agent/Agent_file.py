"""
Agent调试启动器
该文件的作用为：
将自定义的Agent功能注册到Agent服务器中，便于在调试时使用
"""

import os
import json
import importlib
from maa.agent.agent_server import AgentServer

# 读取 custom.json 文件
def load_custom_agents():
    agent_path = os.path.dirname(os.path.abspath(__file__))
    custom_json_path = os.path.join(agent_path, "custom.json")
    
    with open(custom_json_path, "r", encoding="utf-8") as f:
        custom_config = json.load(f)
    
    for agent_name, agent_info in custom_config.items():
        if agent_info["type"] == "action":
            # 解析文件路径
            file_path = agent_info["file_path"].replace("{agent_path}", agent_path)
            # 转换为模块路径
            module_path = file_path.replace("\\", ".").replace(".py", "")
            # 移除路径前缀，只保留模块名部分
            module_path = module_path.split("agent.")[-1]
            
            # 动态导入模块
            module = importlib.import_module(module_path)
            # 获取类
            class_name = agent_info["class"]
            agent_class = getattr(module, class_name)
            
            # 动态创建代理类并注册
            agent_proxy_class = type(f"Agent_{class_name}", (agent_class,), {})
            AgentServer.custom_action(agent_name)(agent_proxy_class)

# 加载自定义 agents
load_custom_agents()