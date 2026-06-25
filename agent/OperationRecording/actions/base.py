# -*- coding: utf-8 -*-
"""
动作基类，具有以下功能：
1. 定义动作执行接口
2. 提供平台访问能力
3. 声明时间线行为元数据
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar, Dict, Optional


@dataclass
class TimelineMeta:
    """
    动作的时间线行为描述，由子类声明

    字段说明：
    - has_duration: 是否支持持续按住（按下-保持-释放），如 move/crouch/charge_attack
    - release_method: stop 时调用 platform.release_action() 的动作名称（如 "move"），仅 has_duration=True 时有效
    - smooth_transition: 是否支持连续同类型动作的平滑过渡（如 move→move 不释放触点/按键），仅 has_duration=True 时有效
    """
    has_duration: bool = False
    release_method: str | None = None
    smooth_transition: bool = False


class ActionBase(ABC):
    """
    动作基类

    子类需要实现：
    - execute(params): 执行动作
    - 可选：start(params): 时间线模式按下（默认 fallback 到 execute）
    - 可选：stop(): 时间线模式释放（默认通过 release_method 调用平台方法）

    属性说明：
    - platform: 平台实例，用于执行底层操作
    - timeline_meta: 时间线行为元数据，子类通过类属性声明
    """

    timeline_meta: ClassVar[TimelineMeta] = TimelineMeta()

    def __init__(self, platform):
        """
        初始化动作

        参数：
        - platform: 平台实例，用于执行底层操作
        """
        self._platform = platform

    @property
    def platform(self):
        """获取平台实例"""
        return self._platform

    @abstractmethod
    def execute(self, params: Dict[str, Any]) -> bool:
        """
        执行动作

        参数：
        - params: 动作参数

        返回值：
        - bool: 是否成功
        """
        pass

    def start(self, params: Dict[str, Any]) -> bool:
        """
        时间线模式：按下（不松开）

        默认 fallback 到 execute()，持续动作子类应覆写此方法。

        参数：
        - params: 动作参数

        返回值：
        - bool: 是否成功
        """
        return self.execute(params)

    def stop(self, direction: Optional[str] = None) -> bool:
        """
        时间线模式：释放

        默认通过 platform.release_action(release_method) 统一释放，持续动作子类可覆写。

        参数：
        - direction: 方向（可选，用于 move 动作的方向感知释放）

        返回值：
        - bool: 是否成功
        """
        if self.timeline_meta.release_method:
            return self._platform.release_action(self.timeline_meta.release_method, direction=direction)
        return True

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """
        验证参数（可选）

        参数：
        - params: 动作参数

        返回值：
        - bool: 参数是否有效
        """
        return True

    def set_context(self, context) -> None:
        """
        设置上下文（可选，仅 run_node 等需要）

        参数：
        - context: MaaFW Context 实例
        """
        pass
