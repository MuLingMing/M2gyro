# -*- coding: utf-8 -*-
"""
配置管理器

功能：
1. 加载/保存 JSON 配置文件
2. 支持点分隔键路径访问（如 "effects.plugins.acceleration"）
3. 提供效果配置的快捷访问方法
"""

import json
import os
from typing import Dict, Any, Optional


class ConfigManager:
    """
    配置管理器

    功能说明：
    1. 配置加载
       - 自动加载 default.json
       - 支持加载用户自定义配置（覆盖默认值）

    2. 配置访问
       - get: 通过点分隔键路径获取配置值
       - set: 通过点分隔键路径设置配置值

    3. 快捷方法
       - get_effects_config: 获取效果插件配置

    使用示例：
    >>> cm = ConfigManager()
    >>> cm.get("effects.enabled")
    True
    """

    def __init__(self, config_dir: Optional[str] = None):
        """
        初始化配置管理器

        参数：
        - config_dir: 配置目录，如果为 None，则使用相对于本模块的 config 目录
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
        """
        加载配置文件

        参数：
        - config_path: 配置文件路径
        """
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
                self._config.update(user_config)

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值

        参数：
        - key: 配置键（支持点分隔路径，如 "effects.plugins.acceleration"）
        - default: 默认值

        返回值：
        - Any: 配置值
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
        """
        设置配置值

        参数：
        - key: 配置键（支持点分隔路径）
        - value: 配置值
        """
        keys = key.split(".")
        config = self._config
        for k in keys[:-1]:
            if k not in config or not isinstance(config[k], dict):
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value

    def save(self, config_path: str):
        """
        保存配置到文件

        参数：
        - config_path: 配置文件路径
        """
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)

    def get_effects_config(self) -> Dict[str, Any]:
        """
        获取效果插件配置

        返回值：
        - Dict: 效果插件配置字典
        """
        return self.get("effects", {})
