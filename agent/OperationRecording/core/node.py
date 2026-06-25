# -*- coding: utf-8 -*-
"""
可组合动作节点

将操作录制脚本建模为节点树，通过 flatten() 展平为事件列表。

节点类型：
- PrimitiveAction: 叶子节点，表示一个具体动作
- Sequence: 串行容器，子节点按顺序执行
- Parallel: 并行容器，子节点同时执行
- AtOffset: 偏移节点，延迟子节点的执行时间

示例：
    Sequence(
        Parallel(
            PrimitiveAction("move", {"direction": "left", "duration": 4.2}),
            AtOffset(2.0, PrimitiveAction("move", {"direction": "forward", "duration": 0.65})),
        ),
        PrimitiveAction("jump", {"duration": 0.3}),
    )
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

from .event import ActionEvent


class ActionNode(ABC):
    """动作节点抽象基类"""

    @abstractmethod
    def flatten(self, offset: float, id_gen: Callable[[], int]) -> List[ActionEvent]:
        """
        将节点树展平为事件列表

        参数：
        - offset: 起始时间偏移（秒）
        - id_gen: action_id 生成器（无参数 → 新 ID）

        返回：
        - List[ActionEvent]: 按时间排序的事件列表
        """
        ...

    @abstractmethod
    def total_duration(self) -> float:
        """
        返回节点的总持续时间

        Sequence: 子节点持续时间之和
        Parallel: 子节点持续时间的最大值
        PrimitiveAction: params["duration"] 或 0
        AtOffset: offset_time + child.total_duration()
        """
        ...


@dataclass
class PrimitiveAction(ActionNode):
    """
    原子动作节点

    字段说明：
    - action_name: 动作名称（如 "move", "jump"）
    - params: 动作参数字典
    - duration: 动作持续时间（秒），从 params["duration"] 提取，0 表示瞬时
    - has_duration: 是否支持持续按住（来自 TimelineMeta.has_duration）
    - smooth_transition: 是否支持连续同类型平滑过渡（来自 TimelineMeta.smooth_transition）
    """

    action_name: str
    params: Dict[str, Any] = field(default_factory=dict)
    duration: float = 0.0
    has_duration: bool = False
    smooth_transition: bool = False

    def flatten(self, offset: float, id_gen: Callable[[], int]) -> List[ActionEvent]:
        actual_duration = self.params.get("duration", self.duration)

        if self.action_name == "wait":
            return []

        if self.has_duration and actual_duration > 0:
            aid = id_gen()
            return [
                ActionEvent(
                    time=offset,
                    phase="start",
                    action_name=self.action_name,
                    params=self.params,
                    action_id=aid,
                    duration=actual_duration,
                ),
                ActionEvent(
                    time=offset + actual_duration,
                    phase="end",
                    action_name=self.action_name,
                    params=self.params,
                    action_id=aid,
                    duration=actual_duration,
                ),
            ]
        else:
            aid = id_gen()
            return [
                ActionEvent(
                    time=offset,
                    phase="execute",
                    action_name=self.action_name,
                    params=self.params,
                    action_id=aid,
                )
            ]

    def total_duration(self) -> float:
        actual_duration = self.params.get("duration", self.duration)
        return actual_duration if isinstance(actual_duration, (int, float)) else 0.0


@dataclass
class Sequence(ActionNode):
    """
    串行容器

    子节点按顺序依次执行，后一个节点在前一个节点结束后开始。
    """

    children: List[ActionNode] = field(default_factory=list)

    def flatten(self, offset: float, id_gen: Callable[[], int]) -> List[ActionEvent]:
        events: List[ActionEvent] = []
        current_offset = offset
        for child in self.children:
            events.extend(child.flatten(current_offset, id_gen))
            current_offset += child.total_duration()
        return events

    def total_duration(self) -> float:
        return sum(c.total_duration() for c in self.children)


@dataclass
class Parallel(ActionNode):
    """
    并行容器

    所有子节点同时开始执行，总持续时间为子节点持续时间的最大值。
    """

    children: List[ActionNode] = field(default_factory=list)

    def flatten(self, offset: float, id_gen: Callable[[], int]) -> List[ActionEvent]:
        events: List[ActionEvent] = []
        for child in self.children:
            events.extend(child.flatten(offset, id_gen))
        return events

    def total_duration(self) -> float:
        if not self.children:
            return 0.0
        return max(c.total_duration() for c in self.children)


@dataclass
class AtOffset(ActionNode):
    """
    偏移节点

    在指定偏移时间后开始执行子节点。
    等效于 Sequence(PrimitiveAction("wait", {"duration": offset_time}), child)。
    """

    offset_time: float
    child: ActionNode

    def flatten(self, offset: float, id_gen: Callable[[], int]) -> List[ActionEvent]:
        return self.child.flatten(offset + self.offset_time, id_gen)

    def total_duration(self) -> float:
        return self.offset_time + self.child.total_duration()
