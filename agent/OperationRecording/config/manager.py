import json
import os
from typing import Dict, Any, Optional


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_dir: Optional[str] = None):
        """初始化配置管理器
        
        Args:
            config_dir: 配置目录，如果为 None，则使用相对于本模块的 config 目录
        """
        if config_dir is None:
            module_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_dir = os.path.join(module_dir, "config")
        
        self._config_dir = config_dir
        self._config: Dict[str, Any] = {}
        self._load_default_config()
    
    def _load_default_config(self):
        """加载默认配置"""
        default_config_path = os.path.join(self._config_dir, "default.json")
        if os.path.exists(default_config_path):
            with open(default_config_path, "r", encoding="utf-8") as f:
                self._config = json.load(f)
    
    def load_config(self, config_path: str):
        """加载配置文件
        
        Args:
            config_path: 配置文件路径
        """
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
                self._config.update(user_config)
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置值
        """
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def set(self, key: str, value: Any):
        """设置配置值
        
        Args:
            key: 配置键
            value: 配置值
        """
        keys = key.split(".")
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
    
    def save(self, config_path: str):
        """保存配置到文件
        
        Args:
            config_path: 配置文件路径
        """
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)
    
    def get_action_config(self, action_name: str) -> Optional[Dict[str, Any]]:
        """获取动作配置
        
        Args:
            action_name: 动作名称
            
        Returns:
            动作配置
        """
        return self.get(f"actions.{action_name}")
    
    def get_platform_config(self, platform_type: str) -> Optional[Dict[str, Any]]:
        """获取平台配置
        
        Args:
            platform_type: 平台类型
            
        Returns:
            平台配置
        """
        return self.get(f"platforms.{platform_type}")
