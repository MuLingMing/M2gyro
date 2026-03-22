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
    # 使用相对于当前文件的路径打开custom.json
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    custom_json_path = os.path.join(current_dir, "custom.json")
    with open(custom_json_path, "r", encoding="utf-8") as f:
        custom_config = json.load(f)
    
    for agent_name, agent_info in custom_config.items():
        
        # 转换为模块路径
        module_path = agent_info["file_path"].replace("/", ".").replace(".py", "")
        module_name = module_path.split(".")[-1]

        # 动态导入模块
        module = __import__(module_path, fromlist=[module_name])
        # try:
        #     module = __import__(module_path, fromlist=[module_name])
        # except ImportError:
        #     print(f"无法导入模块 {module_path}")
        #     continue
        # 获取类
        class_name = agent_info["class"]
        agent_class = getattr(module, class_name)
        
        # 动态创建代理类并注册
        agent_proxy_class = type(f"Agent_{class_name}", (agent_class,), {})
        
        if agent_info["type"] == "action":
            AgentServer.custom_action(agent_name)(agent_proxy_class)
        elif agent_info["type"] == "recognition":
            AgentServer.custom_recognition(agent_name)(agent_proxy_class)

        # try:
        #     if agent_info["type"] == "action":
        #         AgentServer.custom_action(agent_name)(agent_proxy_class)
        #         print(f"成功注册 action 代理 {agent_name}")
        #     elif agent_info["type"] == "recognition":
        #         AgentServer.custom_recognition(agent_name)(agent_proxy_class)
        #         print(f"成功注册 recognition 代理 {agent_name}")
        # except Exception as e:
        #     print(f"注册代理 {agent_name} 失败: {e}")
        #     continue
        
# 加载自定义 agents
load_custom_agents()