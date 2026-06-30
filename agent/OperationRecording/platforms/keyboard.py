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

import json
import os
import time
from typing import Dict, List, Optional, Any
from maa.controller import Controller
from .base import PlatformBase

# 配置文件目录
_CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")


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
    _action_key_map: Dict[str, List[str]] = {
        "jump_button": ["Space"],
    }
    _button_config_file: Optional[str] = None

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

    def __init__(self, platform_controller: Controller, context: Optional[Any] = None):
        super().__init__(platform_controller, context=context)
        self._active_keys: set[int] = set()
        self._active_touch: bool = False
        self._generic_contact: int = 9
        self._turn_config: Dict[str, float] = {"min_duration_ms": 50, "max_duration_ms": 500}
        self._load_button_config()

    def _load_button_config(self) -> None:
        """从 JSON 配置文件加载按键配置"""
        if self._button_config_file is None:
            return
        config_path = os.path.join(_CONFIG_DIR, self._button_config_file)
        if not os.path.exists(config_path):
            return
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except (json.JSONDecodeError, OSError):
            return

        if "key_codes" in config:
            self._key_codes = config["key_codes"]
        if "action_key_map" in config:
            self._action_key_map = config["action_key_map"]

        if "turn_config" in config:
            self._turn_config = config["turn_config"]

    # ===== 原子操作实现 =====

    def press_key(self, key: str, duration: float) -> bool:
        """按键并等待指定时间后释放（duration=0 时只按不松）"""
        return self.hold_key(key, duration)

    def hold_key(self, key: str, duration: float) -> bool:
        """
        按住按键

        duration > 0 时等待后自动释放；duration = 0 时只按不松，需后续调用 release_key 释放。
        """
        controller = self._get_valid_controller()
        if controller is None:
            return False
        try:
            key_code = self._key_codes.get(key)
            if key_code is None:
                return False
            controller.post_key_down(key_code).wait()
            self._active_keys.add(key_code)
            if duration > 0:
                time.sleep(duration)
                controller.post_key_up(key_code).wait()
                self._active_keys.discard(key_code)
            return True
        except Exception:
            return False

    def release_interact(self, interaction_type: str = "default") -> bool:
        """
        释放交互动作的按键

        参数：
        - interaction_type: 交互类型

        返回值：
        - bool: 是否成功释放
        """
        type_key_map = {
            "default": "F",
            "GrapplingHook": "T",
            "E_skill": "E",
            "Q_skill": "R",
            "pet": "Z",
        }
        key = type_key_map.get(interaction_type, "F")
        return self.release_key(key)

    def release_key(self, key: str) -> bool:
        controller = self._get_valid_controller()
        if controller is None:
            return False
        try:
            key_code = self._key_codes.get(key)
            if key_code is None:
                return False
            controller.post_key_up(key_code).wait()
            self._active_keys.discard(key_code)
            return True
        except Exception:
            return False

    def touch_hold(self, x: int, y: int, duration: float = 0) -> bool:
        """按住屏幕指定坐标（通过触控 API 实现）"""
        controller = self._get_valid_controller()
        if controller is None:
            return False
        try:
            x = max(0, min(x, 1279))
            y = max(0, min(y, 719))
            controller.post_touch_down(x, y, self._generic_contact, 1).wait()
            self._active_touch = True
            if duration > 0:
                time.sleep(duration)
                controller.post_touch_up(self._generic_contact).wait()
                self._active_touch = False
            return True
        except Exception:
            return False

    def release_touch(self) -> bool:
        """释放 touch_hold 按下的触点"""
        controller = self._get_valid_controller()
        if controller is None:
            return False
        try:
            if self._active_touch:
                controller.post_touch_up(self._generic_contact).wait()
                self._active_touch = False
                return True
            return False
        except Exception:
            return False

    def click(self, x: int, y: int) -> bool:
        controller = self._get_valid_controller()
        if controller is None:
            return False
        try:
            controller.post_click(x, y).wait()
            return True
        except Exception:
            return False

    def swipe(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float) -> bool:
        controller = self._get_valid_controller()
        if controller is None:
            return False
        try:
            controller.post_swipe(start_x, start_y, end_x, end_y, int(duration * 1000)).wait()
            return True
        except Exception:
            return False

    def release_all(self) -> bool:
        controller = self._get_valid_controller()
        if controller is None:
            return False
        try:
            for key_code in list(self._active_keys):
                controller.post_key_up(key_code).wait()
            self._active_keys.clear()
            if self._active_touch:
                controller.post_touch_up(self._generic_contact).wait()
                self._active_touch = False
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
        controller = self._get_valid_controller()
        if controller is None:
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
                controller.post_key_down(key_code).wait()
                self._active_keys.add(key_code)

        if duration > 0:
            time.sleep(duration)
        return True

    def jump(self, duration: float = 0.1) -> bool:
        return self.hold_key("Space", duration)

    def dodge(self, direction: Optional[str] = None) -> bool:
        controller = self._get_valid_controller()
        if controller is None:
            return False
        try:
            if direction:
                dir_key_map = {"forward": "W", "backward": "S", "left": "A", "right": "D"}
                dir_key = dir_key_map.get(direction)
                if dir_key:
                    dir_code = self._key_codes.get(dir_key)
                    shift_code = self._key_codes.get("Shift")
                    if dir_code is not None and shift_code is not None:
                        controller.post_key_down(dir_code).wait()
                        self._active_keys.add(dir_code)
                        time.sleep(0.05)
                        try:
                            controller.post_key_down(shift_code).wait()
                            self._active_keys.add(shift_code)
                            time.sleep(0.1)
                        finally:
                            controller.post_key_up(shift_code).wait()
                            self._active_keys.discard(shift_code)
                            controller.post_key_up(dir_code).wait()
                            self._active_keys.discard(dir_code)
                        return True
                return False
            else:
                return self.press_key("Shift", 0.1)
        except Exception:
            return False

    def turn(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: Optional[float] = None) -> bool:
        controller = self._get_valid_controller()
        if controller is None:
            return False
        try:
            if duration is not None:
                duration_ms = int(duration)
            else:
                min_dur = int(self._turn_config.get("min_duration_ms", 50))
                max_dur = int(self._turn_config.get("max_duration_ms", 500))
                dx = abs(end_x - start_x)
                duration_ms = max(min_dur, min(dx * 2, max_dur))
            controller.post_swipe(start_x, start_y, end_x, end_y, duration_ms).wait()
            return True
        except Exception:
            return False

    def interact(self, interaction_type: str = "default", duration: float = 0.1) -> bool:
        return self.hold_key("F", duration)

    def grappling_hook(self, duration: float = 0.1) -> bool:
        return self.hold_key("T", duration)

    def e_skill(self, duration: float = 0.1) -> bool:
        return self.hold_key("E", duration)

    def q_skill(self, duration: float = 0.1) -> bool:
        return self.hold_key("R", duration)

    def pet(self, duration: float = 0.1) -> bool:
        return self.hold_key("Z", duration)

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
        controller = self._get_valid_controller()
        if controller is None:
            return False
        if action_name != "move":
            return False

        # 1. 先按下新方向按键（如果在旧方向释放前按下，可保证无缝衔接）
        if new_direction:
            new_keys = self._DIRECTION_KEYS.get(new_direction, [])
            for key in new_keys:
                key_code = self._key_codes.get(key)
                if key_code is not None and key_code not in self._active_keys:
                    controller.post_key_down(key_code).wait()
                    self._active_keys.add(key_code)

        # 2. 再释放旧方向按键
        old_keys = self._DIRECTION_KEYS.get(old_direction, [])
        for key in old_keys:
            key_code = self._key_codes.get(key)
            if key_code is not None and key_code in self._active_keys:
                controller.post_key_up(key_code).wait()
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
        controller = self._get_valid_controller()
        if controller is None:
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
                        controller.post_key_up(key_code).wait()
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
                        controller.post_key_up(key_code).wait()
                        self._active_keys.discard(key_code)
                        released = True
                return released
        except Exception:
            return False
