from abc import ABC, abstractmethod
from typing import Optional, Union
from maa.controller import Controller
from maa.context import Context


class PlatformBase(ABC):
    """平台抽象基类"""

    def __init__(self, platform_context: Controller):
        """初始化平台

        Args:
            platform_context: 控制器实例
        """
        self._platform_context = platform_context
        self._controller_type = "unknown"

    @abstractmethod
    def move(self, direction: str, duration: float) -> bool:
        """移动

        Args:
            direction: 方向 (forward, backward, left, right)
            duration: 持续时间

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    def jump(self) -> bool:
        """跳跃

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    def dodge(self, direction: Optional[str] = None) -> bool:
        """闪避

        Args:
            direction: 方向 (可选)

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    def turn(self, angle: float) -> bool:
        """转向

        Args:
            angle: 角度

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    def interact(self, interaction_type: str) -> bool:
        """交互

        Args:
            interaction_type: 交互类型

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    def spiral_leap(self) -> bool:
        """螺旋飞跃

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    def crouch(self) -> bool:
        """下蹲

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    def charge_attack(self, duration: float, x: Optional[int] = None, y: Optional[int] = None) -> bool:
        """蓄力攻击

        Args:
            duration: 蓄力持续时间（秒）
            x: 蓄力坐标X（可选，用于ADB平台）
            y: 蓄力坐标Y（可选，用于ADB平台）

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    def press_key(self, key: str, duration: float) -> bool:
        """按键

        Args:
            key: 键位
            duration: 持续时间

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    def release_key(self, key: str) -> bool:
        """释放键位

        Args:
            key: 键位

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    def click(self, x: int, y: int) -> bool:
        """点击

        Args:
            x: X坐标
            y: Y坐标

        Returns:
            是否成功
        """
        pass

    @abstractmethod
    def swipe(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float) -> bool:
        """滑动

        Args:
            start_x: 起始X坐标
            start_y: 起始Y坐标
            end_x: 结束X坐标
            end_y: 结束Y坐标
            duration: 持续时间

        Returns:
            是否成功
        """
        pass

    def release_all(self) -> bool:
        """释放所有按键

        Returns:
            是否成功
        """
        return True