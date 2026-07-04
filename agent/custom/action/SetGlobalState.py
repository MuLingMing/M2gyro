# -*- coding: utf-8 -*-
"""
设置自定义识别器/执行器的类级全局状态

功能说明：
1. 通过参数指定目标类名和属性名，使用 setattr 设置类级全局变量
2. 支持一次设置多个类的多个属性
3. 自动从 Agent_file._CLASS_REGISTRY 查找目标类

典型使用场景：
- 在任务开始前统一配置各识别器的输出频率
- 重置识别器的轮次状态
- 设置任何自定义组件的类级参数

Pipeline 使用示例（扁平格式，与 attach 格式一致）：
{
    "InitGlobalState": {
        "recognition": "DirectHit",
        "action": "SetGlobalState",
        "custom_action_param": {
            "RoundTracker._logger_count": 5
        },
        "next": ["MainTask"]
    }
}
"""

import json
from typing import Any, Dict

from maa.context import Context
from maa.custom_action import CustomAction
from param_merger import ParamMerger
from utils.logger import logger


class SetGlobalState(CustomAction):
    """
    设置自定义识别器/执行器的类级全局状态

    注册方式：通过 agent/custom.json 动态注册

    参数格式（custom_action_param，与 attach 格式一致）：
    {
        "类名.属性名": 属性值,
        ...
    }

    字段说明：
    - 类名.属性名: 使用点分隔，格式为 "类名.属性名"
      - 类名必须在 _CLASS_REGISTRY 中注册
      - 属性名必须以 "_" 开头（类级全局状态惯例）
    - 属性值: 支持 int、float、str、bool、list、dict、null

    注意事项：
    - 仅支持设置已注册的类（通过 custom.json 注册的自定义组件）
    - 属性名建议以 "_" 开头，与项目中类级全局状态的命名惯例一致
    - 设置 dict 类型时会直接替换，不会合并
    """

    def run(
        self, context: Context, argv: CustomAction.RunArg
    ) -> CustomAction.RunResult:
        """
        执行设置类级全局状态

        参数:
        - context: MaaFramework 上下文对象
        - argv: 运行参数，包含 custom_action_param

        返回值:
        - CustomAction.RunResult: 执行结果

        执行流程:
        1. 解析参数（扁平格式：类名.属性名 -> 值）
        2. 转换为嵌套格式（类名 -> {属性名 -> 值}）
        3. 遍历每个目标类
        4. 查找类对象并设置属性
        """
        raw_param = argv.custom_action_param

        # 解析 custom_action_param（扁平格式）
        flat_params: Dict[str, Any] = {}
        if raw_param:
            try:
                flat_params = (
                    json.loads(raw_param) if isinstance(raw_param, str) else raw_param
                )
            except json.JSONDecodeError as e:
                logger.error(f"SetGlobalState: 参数解析失败: {e}")

        if not isinstance(flat_params, dict):
            flat_params = {}

        # 读取 attach 参数（同样是扁平格式）
        if node_data := context.get_node_data(argv.node_name):
            attach_params = node_data.get("attach", {})
        else:
            attach_params = {}

        # 合并参数：attach 为基础，custom_action_param 覆盖
        if not flat_params and not attach_params:
            return CustomAction.RunResult(success=True)

        if attach_params:
            merged_flat = ParamMerger.merge(
                "action", flat_params, attach_params
            )
        else:
            merged_flat = flat_params

        if not merged_flat:
            return CustomAction.RunResult(success=True)

        # 将扁平格式转换为嵌套格式：类名.属性名 -> {类名: {属性名: 值}}
        params: Dict[str, Dict[str, Any]] = {}
        for key, value in merged_flat.items():
            if "." not in key:
                logger.warning(
                    f"SetGlobalState: 参数键 '{key}' 格式错误，应为 '类名.属性名'，已跳过"
                )
                continue

            class_name, attr_name = key.split(".", 1)
            if class_name not in params:
                params[class_name] = {}
            params[class_name][attr_name] = value

        # 延迟导入避免循环依赖
        from Agent_file import get_class_registry

        registry = get_class_registry()

        for class_name, attrs in params.items():
            # 查找目标类
            cls = registry.get(class_name)
            if cls is None:
                available = list(registry.keys())
                logger.error(
                    f"SetGlobalState: 未找到类 '{class_name}'，"
                    f"可用的类: {available}"
                )
                continue

            # 设置属性
            for attr_name, value in attrs.items():
                if not hasattr(cls, attr_name):
                    logger.warning(
                        f"SetGlobalState: {class_name} 无属性 '{attr_name}'，已跳过"
                    )
                    continue

                old_value = getattr(cls, attr_name)
                setattr(cls, attr_name, value)
                logger.debug(
                    f"SetGlobalState: {class_name}.{attr_name}: {old_value} -> {value}"
                )

        return CustomAction.RunResult(success=True)
