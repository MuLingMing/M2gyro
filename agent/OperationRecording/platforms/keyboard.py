# -*- coding: utf-8 -*-
"""
键盘平台家族基类

功能：
1. 实现原子操作（press_key/release_key/click/swipe/release_all）
2. 提供业务方法的键盘默认实现
3. 管理按键状态跟踪（_active_keys）
4. 子类只需提供 _key_codes 映射即可

子类示例：
    @register_platform("desktop")
    class DesktopPlatform(KeyboardPlatform):
        _key_codes = {"W": 0x57, "A": 0x41, ...}
        _action_key_map = {"move": ["W","A","S","D"], "crouch": ["C"], "charge_attack": ["MouseLeft"]}
"""

import time
from typing import Dict, List, Optional
from maa.controller import Controller
from .base import PlatformBase


class KeyboardPlatform(PlatformBase):
    """键盘平台家族基类

    子类需提供：
    - _key_codes: Dict[str, int] — 按键名到虚拟键码的映射
    - _action_key_map: Dict[str, List[str]] — 动作名到按键名列表的映射（用于 release_action）

    内置方向→按键列表映射（_DIRECTION_KEYS）：
    支持 4 基本方向 + 4 对角方向（45°），与 TouchPlatform 一致。
    子类可按需覆写以重定向按键（如 Mac 平台）。
    """

    _key_codes: Dict[str, int] = {}
    _action_key_map: Dict[str, List[str]] = {}

    # 方向 → 按键列表映射
    # 4 基本方向（单键）+ 4 对角方向（双键组合），与 touch.py _get_joystick_directions 对齐
    _DIRECTION_KEYS: Dict[str, List[str]] = {
        # 4 基本方向
        "forward": ["W"],
        "backward": ["S"],
        "left": ["A"],
        "right": ["D"],
        # 4 对角方向（45°）
        "forward_left": ["W", "A"],
        "forward_right": ["W", "D"],
        "backward_left": ["S", "A"],
        "backward_right": ["S", "D"],
    }

    def __init__(self, platform_controller: Controller):
        super().__init__(platform_controller)
        self._active_keys: set[int] = set()

    # ===== 原子操作实现 =====

    def press_key(self, key: str, duration: float) -> bool:
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
        if self._controller is None:
            return False
        try:
            key_code = self._key_codes.get(key)
            if key_code is None:
                return False
            self._controller.post_key_up(key_code).wait()
            self._active_keys.discard(key_code)
            return True
        except Exception:
            return False

    def click(self, x: int, y: int) -> bool:
        if self._controller is None:
            return False
        try:
            self._controller.post_click(x, y).wait()
            return True
        except Exception:
            return False

    def swipe(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float) -> bool:
        if self._controller is None:
            return False
        try:
            self._controller.post_swipe(start_x, start_y, end_x, end_y, int(duration * 1000)).wait()
            return True
        except Exception:
            return False

    def release_all(self) -> bool:
        if self._controller is None:
            return False
        try:
            for key_code in list(self._active_keys):
                self._controller.post_key_up(key_code).wait()
            self._active_keys.clear()
            return True
        except Exception:
            return False

    # ===== 业务方法默认实现（键盘语义） =====

    def move(self, direction: str, duration: float) -> bool:
        """
        移动操作

        参数：
        - direction: 移动方向（forward/backward/left/right
                     + forward_left/forward_right/backward_left/backward_right）
        - duration: 持续时间（秒），0 表示只按下不松开

        返回值：
        - bool: 是否成功

        说明：
        - 支持 8 个方向：4 基本方向（单键）+ 4 对角方向（双键同时按下）
        - 移除互斥逻辑，支持多键同时按下
        - duration > 0 时会 sleep 等待
        - 未知方向返回 False
        """
        if self._controller is None:
            return False
        keys = self._DIRECTION_KEYS.get(direction)
        if not keys:
            return False

        # 依次按下方向对应的所有按键（对角方向需要同时按住两个键）
        for key in keys:
            key_code = self._key_codes.get(key)
            if key_code is None:
                return False
            if key_code not in self._active_keys:
                self._controller.post_key_down(key_code).wait()
                self._active_keys.add(key_code)

        if duration > 0:
            time.sleep(duration)
        return True

    def jump(self) -> bool:
        return self.press_key("Space", 0.1)

    def dodge(self, direction: Optional[str] = None) -> bool:
        if self._controller is None:
            return False
        try:
            if direction:
                dir_key_map = {"forward": "W", "backward": "S", "left": "A", "right": "D"}
                dir_key = dir_key_map.get(direction)
                if dir_key:
                    dir_code = self._key_codes.get(dir_key)
                    shift_code = self._key_codes.get("Shift")
                    if dir_code is not None and shift_code is not None:
                        self._controller.post_key_down(dir_code).wait()
                        self._active_keys.add(dir_code)
                        time.sleep(0.05)
                        try:
                            self._controller.post_key_down(shift_code).wait()
                            self._active_keys.add(shift_code)
                            time.sleep(0.1)
                        finally:
                            self._controller.post_key_up(shift_code).wait()
                            self._active_keys.discard(shift_code)
                            self._controller.post_key_up(dir_code).wait()
                            self._active_keys.discard(dir_code)
                        return True
                return False
            else:
                return self.press_key("Shift", 0.1)
        except Exception:
            return False

    def turn(self, angle: float) -> bool:
        if self._controller is None:
            return False
        try:
            center_x, center_y = 640, 360
            pixels_per_degree = 10
            dx = int(angle * pixels_per_degree)
            if dx == 0:
                return True
            start_x = center_x
            end_x = max(0, min(center_x + dx, 1279))
            duration_ms = max(50, min(abs(dx) * 2, 500))
            self._controller.post_swipe(start_x, center_y, end_x, center_y, duration_ms).wait()
            return True
        except Exception:
            return False

    def interact(self, interaction_type: str) -> bool:
        return self.press_key("F", 0.1)

    def spiral_leap(self) -> bool:
        return self.press_key("Q", 0.1)

    def crouch(self, duration: float = 0.1) -> bool:
        return self.press_key("C", duration)

    def charge_attack(self, duration: float, x: Optional[int] = None, y: Optional[int] = None) -> bool:
        return self.press_key("MouseLeft", duration)

    def cleanup_direction(self, action_name: str, old_direction: str, new_direction: Optional[str] = None) -> bool:
        """
        清理动作方向状态（用于连续 move 的平滑过渡）

        先按下新方向按键，再释放旧方向按键，确保始终有按键保持，
        避免角色在方向切换时短暂停止。

        参数：
        - action_name: 动作名称
        - old_direction: 旧方向
        - new_direction: 新方向（用于先按新键再松旧键）

        返回值：
        - bool: 是否成功
        """
        if self._controller is None:
            return False
        if action_name != "move":
            return False

        # 1. 先按下新方向按键（如果在旧方向释放前按下，可保证无缝衔接）
        if new_direction:
            new_keys = self._DIRECTION_KEYS.get(new_direction, [])
            for key in new_keys:
                key_code = self._key_codes.get(key)
                if key_code is not None and key_code not in self._active_keys:
                    self._controller.post_key_down(key_code).wait()
                    self._active_keys.add(key_code)

        # 2. 再释放旧方向按键
        old_keys = self._DIRECTION_KEYS.get(old_direction, [])
        for key in old_keys:
            key_code = self._key_codes.get(key)
            if key_code is not None and key_code in self._active_keys:
                self._controller.post_key_up(key_code).wait()
                self._active_keys.discard(key_code)

        return True

    # ===== 释放方法 =====

    def release_action(self, action_name: str, direction: Optional[str] = None) -> bool:
        """
        释放动作

        参数：
        - action_name: 动作名称
        - direction: 方向（可选，用于 move 动作的方向感知释放）

        返回值：
        - bool: 是否成功释放

        说明：
        - move 动作 + direction：只释放指定方向的键（支持 8 方向，对角方向释放所有相关键）
        - move 动作 + 无 direction：释放所有 WASD 键
        - 其他动作：释放所有相关按键
        """
        if self._controller is None:
            return False
        try:
            if action_name == "move" and direction:
                # 方向感知释放：只释放指定方向的键（对角方向同时释放多个键）
                keys = self._DIRECTION_KEYS.get(direction)
                if not keys:
                    return False
                released = False
                for key in keys:
                    key_code = self._key_codes.get(key)
                    if key_code is not None and key_code in self._active_keys:
                        self._controller.post_key_up(key_code).wait()
                        self._active_keys.discard(key_code)
                        released = True
                return released
            else:
                # 非 move 动作或无方向参数：释放所有相关按键
                keys = self._action_key_map.get(action_name)
                if keys is None:
                    return False
                released = False
                for key in keys:
                    key_code = self._key_codes.get(key)
                    if key_code is not None and key_code in self._active_keys:
                        self._controller.post_key_up(key_code).wait()
                        self._active_keys.discard(key_code)
                        released = True
                return released
        except Exception:
            return False
