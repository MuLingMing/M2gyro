"""
Agent调试启动器
该文件的作用为：
将自定义的Agent功能注册到Agent服务器中，便于在调试时使用
"""

import os
import json
import importlib
from typing import Dict
from maa.agent.agent_server import AgentServer
from utils.logger import logger

# 全局类注册表：类名 -> 类对象
# 供 SetGlobalState 等自定义动作查找目标类
_CLASS_REGISTRY: Dict[str, type] = {}


def get_class_registry() -> Dict[str, type]:
    """
    获取全局类注册表

    返回值:
    - Dict[str, type]: 类名到类对象的映射
    """
    return _CLASS_REGISTRY


# 读取 custom.json 文件
def load_custom_agents():
    # 使用相对于当前文件的路径打开custom.json
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    custom_json_path = os.path.join(current_dir, "custom.json")
    with open(custom_json_path, "r", encoding="utf-8") as f:
        custom_config = json.load(f)
    
    for agent_name, agent_info in custom_config.items():

        try:
            # 转换为模块路径
            module_path = agent_info["file_path"].replace("/", ".")[:-3]
            module_name = module_path.split(".")[-1]

            # 动态导入模块
            module = __import__(module_path, fromlist=[module_name])

            # 获取类
            class_name = agent_info["class"]
            agent_class = getattr(module, class_name)

        except (ImportError, AttributeError, KeyError) as e:
            logger.error(f"Agent_file: 加载组件 {agent_name} 失败，已跳过: {e}")
            continue

        # 动态创建代理类并注册
        agent_proxy_class = type(f"Agent_{class_name}", (agent_class,), {})

        # 注册到全局类注册表（存原始类，供 SetGlobalState 等按类名查找）
        _CLASS_REGISTRY[class_name] = agent_class

        try:
            if agent_info["type"] == "action":
                AgentServer.custom_action(agent_name)(agent_proxy_class)
            elif agent_info["type"] == "recognition":
                AgentServer.custom_recognition(agent_name)(agent_proxy_class)
        except Exception as e:
            logger.error(f"Agent_file: 注册代理 {agent_name} 失败，已跳过: {e}")
            continue
        
# 加载自定义 agents
load_custom_agents()