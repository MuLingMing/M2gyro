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
    """

    _key_codes: Dict[str, int] = {}
    _action_key_map: Dict[str, List[str]] = {}

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
        if self._controller is None:
            return False
        key_map = {"forward": "W", "backward": "S", "left": "A", "right": "D"}
        key = key_map.get(direction)
        if not key:
            return False

        key_code = self._key_codes.get(key)
        if key_code is None:
            return False

        wasd_keys = {"W", "A", "S", "D"}
        wasd_codes = {self._key_codes.get(k) for k in wasd_keys}
        wasd_codes.discard(None)
        for code in wasd_codes:
            if code != key_code and code in self._active_keys:
                self._controller.post_key_up(code).wait()
                self._active_keys.discard(code)

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

    # ===== 释放方法 =====

    def release_action(self, action_name: str) -> bool:
        if self._controller is None:
            return False
        try:
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
