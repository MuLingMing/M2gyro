# -*- coding: utf-8 -*-
"""
平台基类

功能：
1. 定义平台的原子操作接口（5 个抽象方法）
2. 定义业务方法接口（非抽象，由家族基类提供默认实现）
3. 提供 release_action 统一释放机制
"""

import time
from abc import ABC, abstractmethod
from typing import Optional
from maa.controller import Controller


class PlatformBase(ABC):
    """平台抽象基类

    原子操作（子类必须实现）：
    - click: 点击坐标
    - swipe: 滑动
    - press_key: 按键
    - release_key: 释放按键
    - release_all: 释放所有

    业务操作（由家族基类提供默认实现，如 KeyboardPlatform/TouchPlatform）：
    - move: 移动
    - jump: 跳跃
    - dodge: 闪避
    - turn: 转向
    - interact: 交互
    - spiral_leap: 螺旋飞跃
    - crouch: 下蹲
    - charge_attack: 蓄力攻击
    """

    def __init__(self, platform_controller: Controller):
        self._controller_type = "unknown"
        self._controller = platform_controller

    @property
    def controller_type(self) -> str:
        """当前控制器类型（'adb' / 'desktop'）"""
        return self._controller_type

    # ===== 原子操作（抽象，子类必须实现） =====

    @abstractmethod
    def click(self, x: int, y: int) -> bool:
        pass

    @abstractmethod
    def swipe(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float) -> bool:
        pass

    @abstractmethod
    def press_key(self, key: str, duration: float) -> bool:
        pass

    @abstractmethod
    def release_key(self, key: str) -> bool:
        pass

    @abstractmethod
    def release_all(self) -> bool:
        pass

    # ===== 业务操作（非抽象，由家族基类提供默认实现） =====

    def move(self, direction: str, duration: float) -> bool:
        raise NotImplementedError(f"{self.__class__.__name__} 未实现 move()，请继承 KeyboardPlatform 或 TouchPlatform")

    def jump(self) -> bool:
        raise NotImplementedError(f"{self.__class__.__name__} 未实现 jump()，请继承 KeyboardPlatform 或 TouchPlatform")

    def dodge(self, direction: Optional[str] = None) -> bool:
        raise NotImplementedError(f"{self.__class__.__name__} 未实现 dodge()，请继承 KeyboardPlatform 或 TouchPlatform")

    def turn(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = None) -> bool:
        raise NotImplementedError(f"{self.__class__.__name__} 未实现 turn()，请继承 KeyboardPlatform 或 TouchPlatform")

    def interact(self, interaction_type: str) -> bool:
        raise NotImplementedError(f"{self.__class__.__name__} 未实现 interact()，请继承 KeyboardPlatform 或 TouchPlatform")

    def spiral_leap(self) -> bool:
        raise NotImplementedError(f"{self.__class__.__name__} 未实现 spiral_leap()，请继承 KeyboardPlatform 或 TouchPlatform")

    def crouch(self, duration: float = 0.1) -> bool:
        raise NotImplementedError(f"{self.__class__.__name__} 未实现 crouch()，请继承 KeyboardPlatform 或 TouchPlatform")

    def charge_attack(self, duration: float, x: Optional[int] = None, y: Optional[int] = None) -> bool:
        raise NotImplementedError(f"{self.__class__.__name__} 未实现 charge_attack()，请继承 KeyboardPlatform 或 TouchPlatform")

    # ===== 通用方法 =====

    def wait(self, duration: float) -> bool:
        time.sleep(duration)
        return True

    def release_action(self, action_name: str, direction: Optional[str] = None) -> bool:
        """
        释放动作

        参数：
        - action_name: 动作名称
        - direction: 方向（可选，用于 move 动作的方向感知释放）

        返回值：
        - bool: 是否成功释放
        """
        return False

    def cleanup_direction(self, action_name: str, old_direction: str, new_direction: Optional[str] = None) -> bool:
        """
        清理动作方向状态（用于连续同类型动作的平滑过渡）

        与 release_action 的区别：不释放底层触点/按键，仅清理方向跟踪状态，
        让后续动作的 start() 可以直接通过 post_touch_move / key 切换实现平滑过渡。

        参数：
        - action_name: 动作名称
        - old_direction: 旧方向
        - new_direction: 新方向（可选，键盘平台可利用此参数先按新键再松旧键）

        返回值：
        - bool: 是否成功
        """
        return True
