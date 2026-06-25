# -*- coding: utf-8 -*-
"""
调度事件数据类

ActionEvent 是调度器的最小执行单元，由 ActionNode.flatten() 生成，
被 EventScheduler 按时间顺序消费。
"""

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class ActionEvent:
    """
    调度事件

    字段说明：
    - time: 相对于 pipeline 开始的时间（秒）
    - phase: 事件阶段
      - "start": 持续动作的按下阶段（与同 action_id 的 "end" 配对）
      - "end":   持续动作的释放阶段
      - "execute": 瞬时动作（无配对）
    - action_name: 动作名称（如 "move", "jump"）
    - params: 动作参数
    - action_id: 动作实例 ID（start/end 事件共享同一 ID，用于配对）
    - priority: 优先级（数值越大越高），默认 0
    - blocking: 执行期间是否阻塞同优先级动作，默认 True
    - duration: 动作持续时间（仅 start 事件携带，用于上下文）
    """

    time: float
    phase: str
    action_name: str
    params: Dict[str, Any] = field(default_factory=dict, compare=False)
    action_id: int = field(default=0, compare=False)
    priority: int = field(default=0, compare=False)
    blocking: bool = field(default=True, compare=False)
    duration: float = field(default=0.0, compare=False)

    def __post_init__(self):
        if self.phase not in ("start", "end", "execute"):
            raise ValueError(f"无效的事件阶段: {self.phase}")
