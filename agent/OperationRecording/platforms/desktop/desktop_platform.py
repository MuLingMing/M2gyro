# -*- coding: utf-8 -*-
"""
桌面平台实现，提供 Windows 平台的游戏操作功能。

功能说明：
1. 方向控制
   - 向前移动 (W键)
   - 向后移动 (S键)
   - 向左移动 (A键)
   - 向右移动 (D键)
2. 基础操作
   - 跳跃 (空格键)
   - 闪避 (Shift键)
   - 转向 (AD键控制)
   - 交互 (F键)
   - 螺旋飞跃 (Q键)
   - 下蹲 (C键)
3. 战斗操作
   - 蓄力攻击 (鼠标左键)
4. 辅助功能
   - 按键按压/释放
   - 点击坐标
   - 滑动操作
   - 释放所有按键（安全停止）
"""

import time
from typing import Optional, Union
from maa.controller import Controller
from maa.context import Context
from ..base import PlatformBase


class DesktopPlatform(PlatformBase):
    """桌面平台实现类
    
    功能说明：
    1. 提供 Windows 桌面游戏的操作接口
    2. 使用虚拟按键码模拟键盘和鼠标操作
    3. 支持按键状态跟踪，确保停止时释放所有按键
    
    参数格式：
    {
        "platform_type": "desktop",
        "controller": Controller实例
    }
    
    字段说明：
    - _key_codes: 虚拟按键码映射表
    - _controller_type: 平台类型标识
    - _controller: MAA控制器实例
    - _active_keys: 当前按下的按键集合
    """

    _key_codes = {
        "W": 0x57,
        "A": 0x41,
        "S": 0x53,
        "D": 0x44,
        "Space": 0x20,
        "Shift": 0x10,
        "F": 0x46,
        "Q": 0x51,
        "C": 0x43,
        "MouseLeft": 0x01,
    }

    def __init__(self, platform_context: Controller):
        """初始化桌面平台
        
        参数：
        - platform_context: MAA控制器或上下文对象
        
        执行流程：
        1. 调用父类初始化
        2. 设置平台类型为 "desktop"
        3. 初始化控制器引用
        4. 初始化按键跟踪集合
        """
        super().__init__(platform_context)
        self._controller_type = "desktop"
        self._controller = None
        self._active_keys: set = set()

        if isinstance(platform_context, Controller):
            self._controller = platform_context
        elif isinstance(platform_context, Context) and hasattr(platform_context, 'tasker'):
            self._controller = platform_context.tasker.controller

    def move(self, direction: str, duration: float) -> bool:
        """执行移动操作
        
        参数：
        - direction: 移动方向 ("forward"/"backward"/"left"/"right")
        - duration: 持续时间（秒）
        
        返回：
        - bool: 是否成功
        
        执行流程：
        1. 根据方向映射到对应按键
        2. 调用 press_key 方法按压指定时间
        """
        key_map = {
            "forward": "W",
            "backward": "S",
            "left": "A",
            "right": "D"
        }
        key = key_map.get(direction)
        if key:
            return self.press_key(key, duration)
        return False

    def jump(self) -> bool:
        """执行跳跃操作
        
        返回：
        - bool: 是否成功
        
        执行流程：
        1. 按压空格键 0.1 秒
        """
        return self.press_key("Space", 0.1)

    def dodge(self, direction: Optional[str] = None) -> bool:
        """执行闪避操作
        
        参数：
        - direction: 闪避方向（可选）
        
        返回：
        - bool: 是否成功
        
        执行流程：
        1. 如果有方向，先移动 0.05 秒
        2. 按压 Shift 键 0.1 秒
        """
        if direction:
            self.move(direction, 0.05)
        return self.press_key("Shift", 0.1)

    def turn(self, angle: float) -> bool:
        """执行转向操作
        
        参数：
        - angle: 转向角度（正数向右转，负数向左转）
        
        返回：
        - bool: 是否成功
        
        执行流程：
        1. 根据角度计算偏移量
        2. 根据偏移方向选择 A 或 D 键
        3. 计算按压时长（最大 0.5 秒）
        4. 执行按键按压
        """
        try:
            dx = int(angle * 5)
            if dx != 0:
                key = "A" if dx < 0 else "D"
                duration = min(abs(dx) * 0.01, 0.5)
                self.press_key(key, duration)
            return True
        except Exception:
            return False

    def interact(self, interaction_type: str) -> bool:
        """执行交互操作
        
        参数：
        - interaction_type: 交互类型（当前未使用）
        
        返回：
        - bool: 是否成功
        
        执行流程：
        1. 按压 F 键 0.1 秒
        """
        return self.press_key("F", 0.1)

    def spiral_leap(self) -> bool:
        """执行螺旋飞跃操作
        
        返回：
        - bool: 是否成功
        
        执行流程：
        1. 按压 Q 键 0.1 秒
        """
        return self.press_key("Q", 0.1)

    def crouch(self) -> bool:
        """执行下蹲操作
        
        返回：
        - bool: 是否成功
        
        执行流程：
        1. 按压 C 键 0.1 秒
        """
        return self.press_key("C", 0.1)

    def charge_attack(self, duration: float, x: Optional[int] = None, y: Optional[int] = None) -> bool:
        """执行蓄力攻击操作
        
        参数：
        - duration: 蓄力时间（秒）
        - x: 目标X坐标（可选）
        - y: 目标Y坐标（可选）
        
        返回：
        - bool: 是否成功
        
        执行流程：
        1. 按下鼠标左键
        2. 记录到活动按键集合
        3. 等待指定蓄力时间
        4. 释放鼠标左键
        """
        if self._controller is None:
            return False
        try:
            key_code = self._key_codes.get("MouseLeft")
            if key_code is None:
                return False
            self._controller.post_key_down(key_code).wait()
            self._active_keys.add(key_code)
            if duration > 0:
                time.sleep(duration)
                self._controller.post_key_up(key_code).wait()
                self._active_keys.discard(key_code)
            return True
        except Exception:
            return False

    def press_key(self, key: str, duration: float) -> bool:
        """按压指定按键
        
        参数：
        - key: 按键名称
        - duration: 持续时间（秒，0表示只按下不释放）
        
        返回：
        - bool: 是否成功
        
        执行流程：
        1. 获取按键虚拟码
        2. 发送按键按下事件
        3. 记录到活动按键集合
        4. 如果有持续时间，等待后发送释放事件
        """
        if self._controller is None:
            return False
        try:
            key_code = self._key_codes.get(key)
            if key_code is None:
                return False
            self._controller.post_key_down(key_code).wait()
            self._active_keys.add(key_code)
            if duration > 0:
                time.sleep(duration)
                self._controller.post_key_up(key_code).wait()
                self._active_keys.discard(key_code)
            return True
        except Exception:
            return False

    def release_key(self, key: str) -> bool:
        """释放指定按键
        
        参数：
        - key: 按键名称
        
        返回：
        - bool: 是否成功
        
        执行流程：
        1. 获取按键虚拟码
        2. 发送按键释放事件
        """
        if self._controller is None:
            return False
        try:
            key_code = self._key_codes.get(key)
            if key_code is None:
                return False
            self._controller.post_key_up(key_code).wait()
            return True
        except Exception:
            return False

    def click(self, x: int, y: int) -> bool:
        """点击指定坐标
        
        参数：
        - x: 目标X坐标
        - y: 目标Y坐标
        
        返回：
        - bool: 是否成功
        
        执行流程：
        1. 发送点击事件到指定坐标
        """
        if self._controller is None:
            return False
        try:
            self._controller.post_click(x, y).wait()
            return True
        except Exception:
            return False

    def swipe(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float) -> bool:
        """执行滑动操作
        
        参数：
        - start_x: 起始X坐标
        - start_y: 起始Y坐标
        - end_x: 结束X坐标
        - end_y: 结束Y坐标
        - duration: 滑动持续时间（秒）
        
        返回：
        - bool: 是否成功
        
        执行流程：
        1. 发送滑动事件，持续时间转换为毫秒
        """
        if self._controller is None:
            return False
        try:
            self._controller.post_swipe(start_x, start_y, end_x, end_y, int(duration * 1000)).wait()
            return True
        except Exception:
            return False

    def release_all(self) -> bool:
        """释放所有按键（安全停止）
        
        返回：
        - bool: 是否成功
        
        执行流程：
        1. 遍历所有活动按键
        2. 逐个发送释放事件
        3. 清空活动按键集合
        """
        if self._controller is None:
            return False
        try:
            for key_code in list(self._active_keys):
                self._controller.post_key_up(key_code).wait()
            self._active_keys.clear()
            return True
        except Exception:
            return False
