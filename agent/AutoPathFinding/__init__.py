# -*- coding: utf-8 -*-
"""
自动寻路模块

功能说明：
1. AutoPathAction: 自动寻路动作器（合并版）
   - 识别场景中的目的地标志（门/菱形），执行选择策略，选出最优目标
   - 根据目标位置调整视角、控制角色移动、处理障碍物
   - 内部循环执行直到到达目标或收到停止信号

支持的目标类型：
- 门类标志（互斥组A）: gold_door, blue_door, red_sword_door, red_door
- 特殊标志（互斥组B）: gold_diamond

支持的选择策略：
- priority: 按优先级排序，同优先级选最近的
- nearest: 始终选择距离最近的目标
- reverse_priority: 反向优先级排序，同优先级选最近的

支持的平台：
- ADB (Android): 虚拟摇杆 + 视角滑动
- Win32 (PC): 方向键（预留）
"""

from .action.AutoPathAction import AutoPathAction

__all__ = ["AutoPathAction"]
