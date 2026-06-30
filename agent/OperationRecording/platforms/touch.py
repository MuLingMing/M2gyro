# -*- coding: utf-8 -*-
"""
触控平台家族基类

功能：
1. 实现原子操作（press_key/release_key/click/swipe/release_all）
2. 提供业务方法的触控默认实现
3. 管理触点状态跟踪（_active_contacts）
4. 子类只需提供 _touch_positions 坐标映射即可

子类示例：
    @register_platform("adb")
    class AdbPlatform(TouchPlatform):
        _touch_positions = {
            "joystick_center": {"x": 225, "y": 536, "contact": 0, "joystick_run_offset": -60},
            "jump_button": {"x": 978, "y": 410, "contact": 1},
            ...
        }
        _generic_contact = 8
"""

import math
import os
import time
import json
from typing import Dict, Any, Optional, Tuple
from maa.controller import Controller
from .base import PlatformBase
from utils.logger import logger
from maa.context import Context as MaaContext

TOUCH_SWIPE_DURATION_MS = 600
# 摇杆首次按下后等待游戏引擎确认的帧数（60fps ≈ 16.7ms/帧，2 帧 = 33ms）
JOYSTICK_TOUCHDOWN_DELAY = 0.033
# 配置文件目录
_CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")


class TouchPlatform(PlatformBase):
    """触控平台家族基类

    子类需提供：
    - _touch_positions: Dict[str, Dict] — 按钮位置配置
      格式: {"button_name": {"x": int, "y": int, "contact": int, ...}}
    - _generic_contact: int — 通用触点 ID
    """

    _touch_positions: Dict[str, Dict[str, Any]] = {}
    _generic_contact: int = 8
    _joystick_offset: int = 72
    _button_config_file: Optional[str] = None
    _touch_contact: str = "generic_touch"

    _key_touch_map: Dict[str, Dict[str, Any]] = {
        "W":     {"position": "joystick_center", "contact": "joystick", "is_joystick": "true"},
        "A":     {"position": "joystick_center", "contact": "joystick", "is_joystick": "true"},
        "S":     {"position": "joystick_center", "contact": "joystick", "is_joystick": "true"},
        "D":     {"position": "joystick_center", "contact": "joystick", "is_joystick": "true"},
        "Space": {"position": "jump_button",     "contact": "jump_button"},
        "F":     {"position": "interact_button",  "contact": "interact_button"},
        "Shift": {"position": "sprint_button",    "contact": "sprint_button"},
        "Q":     {"position": "spiral_leap_button", "contact": "spiral_leap_button"},
        "C":     {"position": "crouch_button",    "contact": "crouch"},
    }

    def __init__(self, platform_controller: Controller, context: Optional[MaaContext] = None):
        super().__init__(platform_controller, context=context)
        self._active_contacts: Dict[str, int] = {}
        self._active_directions: set = set()  # 跟踪活跃的移动方向
        self._touch_positions_config: Dict[str, Dict[str, Any]] = {}  # 原始配置（含 w, h）
        self._turn_config: Dict[str, float] = {"swipe_duration_ms": 70}
        self._load_button_config()

    # ===== 内部工具方法 =====

    def _load_button_config(self) -> None:
        """从 JSON 配置文件加载按钮配置"""
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

        # 加载触控位置
        positions: Dict[str, Dict[str, Any]] = {}
        raw_config: Dict[str, Dict[str, Any]] = {}
        for name, pos in config.items():
            if name in ("key_touch_map", "generic_contact"):
                continue
            if isinstance(pos, dict) and "x" in pos and "y" in pos:
                positions[name] = {
                    "x": pos["x"],
                    "y": pos["y"],
                    "contact": pos.get("contact", self._generic_contact),
                }
                if "joystick_run_offset" in pos:
                    positions[name]["joystick_run_offset"] = pos["joystick_run_offset"]
                raw_config[name] = dict(pos)  # 保留原始配置（含 w, h）

        if positions:
            self._touch_positions = positions
            self._touch_positions_config = raw_config

        # 加载 key_touch_map
        if "key_touch_map" in config:
            self._key_touch_map = config["key_touch_map"]

        # 加载 generic_contact
        if "generic_contact" in config:
            self._generic_contact = config["generic_contact"]

        # 加载 turn_config
        if "turn_config" in config:
            self._turn_config = config["turn_config"]

    def _get_position(self, position_name: str, default_x: int, default_y: int) -> Tuple[int, int]:
        position = self._touch_positions.get(position_name, {})
        x = position.get("x", default_x)
        y = position.get("y", default_y)
        return (x, y)

    def _get_contact(self, position_name: str) -> int:
        position_config = self._touch_positions.get(position_name, {})
        return position_config.get("contact", self._generic_contact)

    def _get_joystick_directions(self) -> Dict[str, Tuple[int, int]]:
        """
        获取摇杆方向坐标映射

        返回值：
        - Dict[str, Tuple[int, int]]: 方向名称到坐标的映射

        说明：
        - 支持 8 个方向：4 基本 + 4 组合
        - 组合方向使用 45° 对角线计算
        """
        cx, cy = self._get_position("joystick_center", 198, 552)
        config = self._touch_positions.get("joystick_center", {})
        run_offset = config.get("joystick_run_offset", -72)

        # 计算 45° 对角线偏移量（0.707 ≈ cos(45°) = sin(45°)）
        diagonal_offset_x = int(self._joystick_offset * 0.707)
        diagonal_offset_y = int(abs(run_offset) * 0.707)

        return {
            # 基本方向
            "forward": (cx, cy + run_offset),
            "backward": (cx, cy - run_offset),
            "left": (cx - self._joystick_offset, cy),
            "right": (cx + self._joystick_offset, cy),
            # 组合方向（45° 对角线）
            "forward_left": (cx - diagonal_offset_x, cy + diagonal_offset_y),
            "forward_right": (cx + diagonal_offset_x, cy + diagonal_offset_y),
            "backward_left": (cx - diagonal_offset_x, cy - diagonal_offset_y),
            "backward_right": (cx + diagonal_offset_x, cy - diagonal_offset_y),
            # 兼容旧的按键映射
            "W": (cx, cy + run_offset),
            "A": (cx - self._joystick_offset, cy),
            "S": (cx, cy - run_offset),
            "D": (cx + self._joystick_offset, cy),
        }

    def _hold_button(self, position_name: str, contact_name: str, duration: float,
                     x: Optional[int] = None, y: Optional[int] = None) -> bool:
        controller = self._get_valid_controller()
        if controller is None:
            return False
        try:
            pos_x, pos_y = self._get_position(position_name, 0, 0)
            x = x if x is not None else pos_x
            y = y if y is not None else pos_y
            x = max(0, min(x, 1279))
            y = max(0, min(y, 719))
            contact = self._get_contact(contact_name)

            controller.post_touch_down(x, y, contact, 1).wait()
            self._active_contacts[contact_name] = contact

            if duration > 0:
                time.sleep(duration)
                controller.post_touch_up(contact).wait()
                if contact_name in self._active_contacts:
                    del self._active_contacts[contact_name]
            return True
        except Exception:
            return False

    def _click_button(self, x: int, y: int, contact: int, hold_time: float = 0.05) -> bool:
        controller = self._get_valid_controller()
        if controller is None:
            return False
        try:
            x = max(0, min(x, 1279))
            y = max(0, min(y, 719))
            controller.post_touch_down(x, y, contact, 1).wait()
            time.sleep(hold_time)
            controller.post_touch_up(contact).wait()
            return True
        except Exception:
            return False

    def _release_button(self, contact_name: str) -> bool:
        """释放指定名称的活跃触点"""
        controller = self._get_valid_controller()
        if controller is None:
            return False
        try:
            if contact_name in self._active_contacts:
                contact = self._active_contacts[contact_name]
                controller.post_touch_up(contact).wait()
                del self._active_contacts[contact_name]
                return True
            return False
        except Exception:
            return False

    def _joystick_move(self, x: int, y: int, duration: float) -> bool:
        controller = self._get_valid_controller()
        if controller is None:
            return False
        try:
            contact = self._get_contact("joystick_center")
            joystick_center_x, joystick_center_y = self._get_position("joystick_center", 198, 552)

            x = max(0, min(x, 1279))
            y = max(0, min(y, 719))

            controller.post_touch_down(joystick_center_x, joystick_center_y, contact, 1).wait()
            time.sleep(JOYSTICK_TOUCHDOWN_DELAY)
            controller.post_touch_move(x, y, contact, 1).wait()

            self._active_contacts["joystick"] = contact

            if duration > 0:
                time.sleep(duration)
                controller.post_touch_up(contact).wait()
                if "joystick" in self._active_contacts:
                    del self._active_contacts["joystick"]

            return True
        except Exception:
            return False

    def _joystick_center(self) -> bool:
        controller = self._get_valid_controller()
        if controller is None:
            return False
        try:
            contact = self._get_contact("joystick_center")
            if "joystick" in self._active_contacts:
                controller.post_touch_up(contact).wait()
                del self._active_contacts["joystick"]
            return True
        except Exception:
            return False

    def _calculate_joystick_position(self, active_directions: set) -> Tuple[int, int]:
        """
        根据活跃方向计算摇杆位置（向量和）

        参数：
        - active_directions: 当前活跃的方向集合

        返回值：
        - Tuple[int, int]: 摇杆目标坐标 (x, y)

        算法：
        1. 将每个方向转换为单位向量
        2. 求向量和
        3. 归一化后乘以摇杆半径
        4. 加上摇杆中心坐标
        """
        # 方向向量映射（屏幕坐标系：x 右正，y 下正）
        direction_vectors = {
            "forward": (0, -1),     # 上
            "backward": (0, 1),     # 下
            "left": (-1, 0),        # 左
            "right": (1, 0),        # 右
        }

        cx, cy = self._get_position("joystick_center", 198, 552)
        config = self._touch_positions.get("joystick_center", {})
        run_offset = abs(config.get("joystick_run_offset", -72))

        # 计算向量和
        sum_x = 0.0
        sum_y = 0.0
        for direction in active_directions:
            vec = direction_vectors.get(direction)
            if vec is not None:
                sum_x += vec[0]
                sum_y += vec[1]

        # 归一化
        norm = math.sqrt(sum_x ** 2 + sum_y ** 2)
        if norm > 0:
            sum_x = sum_x / norm * run_offset
            sum_y = sum_y / norm * run_offset

        return (int(cx + sum_x), int(cy + sum_y))

    # ===== 原子操作实现 =====

    def press_key(self, key: str, duration: float) -> bool:
        """按键并等待指定时间后释放（duration=0 时只按不松）"""
        return self.hold_key(key, duration)

    def hold_key(self, key: str, duration: float) -> bool:
        """
        按住按键（触控映射）

        duration > 0 时等待后自动释放；duration = 0 时只按不松，需后续调用 release_key 释放。
        """
        mapping = self._key_touch_map.get(key)
        if not mapping:
            return False

        if mapping.get("is_joystick") == "true":
            directions = self._get_joystick_directions()
            target = directions.get(key)
            if target:
                return self._joystick_move(target[0], target[1], duration)
            return False

        position_name = mapping["position"]
        contact_name = mapping["contact"]

        return self._hold_button(position_name, contact_name, duration)

    def touch_hold(self, x: int, y: int, duration: float = 0) -> bool:
        """
        按住屏幕指定坐标

        duration > 0 时等待后自动释放；duration = 0 时只按不松，需后续调用 release_touch 释放。
        """
        return self._hold_button("", self._touch_contact, duration, x, y)

    def release_touch(self) -> bool:
        """释放 touch_hold 按下的触点"""
        return self._release_button(self._touch_contact)

    def release_key(self, key: str) -> bool:
        controller = self._get_valid_controller()
        if controller is None:
            return False
        try:
            mapping = self._key_touch_map.get(key)
            if not mapping:
                return False
            contact_name = mapping["contact"]

            if contact_name in self._active_contacts:
                contact = self._active_contacts[contact_name]
                controller.post_touch_up(contact).wait()
                del self._active_contacts[contact_name]
                return True
            return False
        except Exception:
            return False

    def click(self, x: int, y: int) -> bool:
        return self._click_button(x, y, self._generic_contact)

    def swipe(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float) -> bool:
        controller = self._get_valid_controller()
        if controller is None:
            return False
        try:
            controller.post_swipe(
                start_x, start_y, end_x, end_y, int(duration * 1000)
            ).wait()
            return True
        except Exception:
            return False

    def release_all(self) -> bool:
        controller = self._get_valid_controller()
        if controller is None:
            return False
        try:
            for contact in list(self._active_contacts.values()):
                controller.post_touch_up(contact).wait()
            self._active_contacts.clear()
            return True
        except Exception:
            return False

    # ===== 业务方法默认实现（触控语义） =====

    def move(self, direction: str, duration: float) -> bool:
        """
        移动操作

        参数：
        - direction: 移动方向（forward/backward/left/right/center）
        - duration: 持续时间（秒），0 表示只按下不松开

        返回值：
        - bool: 是否成功

        说明：
        - 维护 _active_directions 集合跟踪活跃方向
        - center 方向会清空所有活跃方向并归位摇杆
        """
        if direction == "center":
            self._active_directions.clear()
            return self._joystick_center()

        directions = self._get_joystick_directions()
        target = directions.get(direction)
        if not target:
            return False

        controller = self._get_valid_controller()
        if controller is None:
            return False

        try:
            # 添加方向到活跃方向集合
            self._active_directions.add(direction)

            # 多方向时合成摇杆位置（如 left + forward → forward_left）
            if len(self._active_directions) > 1:
                x, y = self._calculate_joystick_position(self._active_directions)
            else:
                x = max(0, min(target[0], 1279))
                y = max(0, min(target[1], 719))

            if "joystick" in self._active_contacts:
                contact = self._active_contacts["joystick"]
                controller.post_touch_move(x, y, contact, 1).wait()
            else:
                contact = self._get_contact("joystick_center")
                joystick_center_x, joystick_center_y = self._get_position("joystick_center", 198, 552)
                controller.post_touch_down(joystick_center_x, joystick_center_y, contact, 1).wait()
                time.sleep(JOYSTICK_TOUCHDOWN_DELAY)
                controller.post_touch_move(x, y, contact, 1).wait()
                self._active_contacts["joystick"] = contact

            if duration > 0:
                time.sleep(duration)
            return True
        except Exception:
            self._active_directions.discard(direction)
            return False

    def jump(self, duration: float = 0.1) -> bool:
        return self._hold_button("jump_button", "jump_button", duration)

    def dodge(self, direction: Optional[str] = None) -> bool:
        controller = self._get_valid_controller()
        if controller is None:
            return False
        try:
            if direction:
                directions = self._get_joystick_directions()
                target = directions.get(direction)
                if target:
                    contact = self._get_contact("joystick_center")
                    joystick_center_x, joystick_center_y = self._get_position("joystick_center", 198, 552)
                    controller.post_touch_down(joystick_center_x, joystick_center_y, contact, 1).wait()
                    controller.post_touch_move(target[0], target[1], contact, 1).wait()
                    time.sleep(0.05)
                    x, y = self._get_position("sprint_button", 1166, 620)
                    sprint_contact = self._get_contact("sprint_button")
                    self._click_button(x, y, sprint_contact)
                    time.sleep(0.1)
                    controller.post_touch_up(contact).wait()
                    return True
                return False
            else:
                x, y = self._get_position("sprint_button", 1166, 620)
                return self._click_button(x, y, self._get_contact("sprint_button"))
        except Exception:
            return False

    def turn(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: Optional[float] = None) -> bool:
        controller = self._get_valid_controller()
        if controller is None:
            return False
        try:
            swipe_duration_ms = int(duration) if duration is not None else int(self._turn_config.get("swipe_duration_ms", 70))
            controller.post_swipe(start_x, start_y, end_x, end_y, swipe_duration_ms).wait()
            return True
        except Exception:
            return False

    def interact(self, interaction_type: str = "default", duration: float = 0.1) -> bool:
        return self._hold_button("interact_button", "interact_button", duration)

    def grappling_hook(self, duration: float = 0.1) -> bool:
        return self._hold_button("grappling_hook_button", "grappling_hook_button", duration)

    def e_skill(self, duration: float = 0.1) -> bool:
        return self._hold_button("e_skill_button", "e_skill_button", duration)

    def q_skill(self, duration: float = 0.1) -> bool:
        return self._hold_button("q_skill_button", "q_skill_button", duration)

    def pet(self, duration: float = 0.1) -> bool:
        return self._hold_button("pet_button", "pet_button", duration)

    def spiral_leap(self) -> bool:
        x, y = self._get_position("spiral_leap_button", 1166, 475)
        return self._click_button(x, y, self._get_contact("spiral_leap_button"))

    def crouch(self, duration: float = 0.1) -> bool:
        return self._hold_button("crouch_button", "crouch", duration)

    def charge_attack(self, duration: float, x: Optional[int] = None, y: Optional[int] = None) -> bool:
        return self._hold_button("charge_attack_button", "charge_attack", duration, x, y)

    # ===== 释放方法 =====

    def cleanup_direction(self, action_name: str, old_direction: str, new_direction: Optional[str] = None) -> bool:
        """
        清理动作方向状态（用于连续 move 的平滑过渡）

        与 release_action 的区别：保留触点，只切换方向跟踪状态。
        先移除旧方向，再添加新方向，然后 post_touch_move 到合成位置。

        参数：
        - action_name: 动作名称
        - old_direction: 旧方向
        - new_direction: 新方向

        返回值：
        - bool: 是否成功
        """
        if action_name == "move" and hasattr(self, '_active_directions'):
            self._active_directions.discard(old_direction)
            if new_direction:
                self._active_directions.add(new_direction)
            controller = self._get_valid_controller()
            if controller is not None and "joystick" in self._active_contacts and self._active_directions:
                try:
                    x, y = self._calculate_joystick_position(self._active_directions)
                    contact = self._active_contacts["joystick"]
                    controller.post_touch_move(x, y, contact, 1).wait()
                except Exception:
                    return False
            return True
        return False

    def release_action(self, action_name: str, direction: Optional[str] = None) -> bool:
        """
        释放动作

        参数：
        - action_name: 动作名称
        - direction: 方向（可选，用于 move 动作的方向感知释放）

        返回值：
        - bool: 是否成功释放

        说明：
        - move 动作 + direction：移除指定方向，重新计算摇杆位置
        - move 动作 + 无 direction：归位摇杆
        - 其他动作：释放对应触点
        """
        controller = self._get_valid_controller()
        if controller is None:
            return False
        try:
            if action_name == "move":
                if direction and hasattr(self, '_active_directions'):
                    # 方向感知释放：移除指定方向，重新计算摇杆位置
                    self._active_directions.discard(direction)
                    if self._active_directions:
                        # 还有其他方向，重新计算摇杆位置
                        position = self._calculate_joystick_position(self._active_directions)
                        contact = self._get_contact("joystick_center")
                        controller.post_touch_move(position[0], position[1], contact, 1).wait()
                    else:
                        # 没有方向了，归位摇杆
                        self._joystick_center()
                    return True
                else:
                    # 无方向参数或无 _active_directions：归位摇杆
                    return self._joystick_center()
            if action_name in self._active_contacts:
                contact = self._active_contacts[action_name]
                controller.post_touch_up(contact).wait()
                del self._active_contacts[action_name]
                return True
            return False
        except Exception:
            return False

    def release_interact(self, interaction_type: str = "default") -> bool:
        """
        释放交互动作的触点

        参数：
        - interaction_type: 交互类型

        返回值：
        - bool: 是否成功释放
        """
        type_contact_map = {
            "default": "interact_button",
            "GrapplingHook": "grappling_hook_button",
            "E_skill": "e_skill_button",
            "Q_skill": "q_skill_button",
            "pet": "pet_button",
        }
        contact_name = type_contact_map.get(interaction_type, "interact_button")
        return self._release_button(contact_name)
