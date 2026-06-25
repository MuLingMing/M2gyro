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
import time
from typing import Dict, Any, Optional, Tuple
from maa.controller import Controller
from .base import PlatformBase

TOUCH_SWIPE_DURATION_MS = 70
# 摇杆首次按下后等待游戏引擎确认的帧数（60fps ≈ 16.7ms/帧，2 帧 = 33ms）
JOYSTICK_TOUCHDOWN_DELAY = 0.033


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

    def __init__(self, platform_controller: Controller):
        super().__init__(platform_controller)
        self._active_contacts: Dict[str, int] = {}
        self._active_directions: set = set()  # 跟踪活跃的移动方向

    # ===== 内部工具方法 =====

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
        if self._controller is None:
            return False
        try:
            pos_x, pos_y = self._get_position(position_name, 0, 0)
            x = x if x is not None else pos_x
            y = y if y is not None else pos_y
            x = max(0, min(x, 1279))
            y = max(0, min(y, 719))
            contact = self._get_contact(contact_name)

            self._controller.post_touch_down(x, y, contact, 1).wait()
            self._active_contacts[contact_name] = contact

            if duration > 0:
                time.sleep(duration)
                self._controller.post_touch_up(contact).wait()
                if contact_name in self._active_contacts:
                    del self._active_contacts[contact_name]
            return True
        except Exception:
            return False

    def _click_button(self, x: int, y: int, contact: int, hold_time: float = 0.05) -> bool:
        if self._controller is None:
            return False
        try:
            x = max(0, min(x, 1279))
            y = max(0, min(y, 719))
            self._controller.post_touch_down(x, y, contact, 1).wait()
            time.sleep(hold_time)
            self._controller.post_touch_up(contact).wait()
            return True
        except Exception:
            return False

    def _joystick_move(self, x: int, y: int, duration: float) -> bool:
        if self._controller is None:
            return False
        try:
            contact = self._get_contact("joystick_center")
            joystick_center_x, joystick_center_y = self._get_position("joystick_center", 198, 552)

            x = max(0, min(x, 1279))
            y = max(0, min(y, 719))

            self._controller.post_touch_down(joystick_center_x, joystick_center_y, contact, 1).wait()
            time.sleep(JOYSTICK_TOUCHDOWN_DELAY)
            self._controller.post_touch_move(x, y, contact, 1).wait()

            self._active_contacts["joystick"] = contact

            if duration > 0:
                time.sleep(duration)
                self._controller.post_touch_up(contact).wait()
                if "joystick" in self._active_contacts:
                    del self._active_contacts["joystick"]

            return True
        except Exception:
            return False

    def _joystick_center(self) -> bool:
        if self._controller is None:
            return False
        try:
            contact = self._get_contact("joystick_center")
            if "joystick" in self._active_contacts:
                self._controller.post_touch_up(contact).wait()
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

    def release_key(self, key: str) -> bool:
        if self._controller is None:
            return False
        try:
            mapping = self._key_touch_map.get(key)
            if not mapping:
                return False
            contact_name = mapping["contact"]

            if contact_name in self._active_contacts:
                contact = self._active_contacts[contact_name]
                self._controller.post_touch_up(contact).wait()
                del self._active_contacts[contact_name]
                return True
            return False
        except Exception:
            return False

    def click(self, x: int, y: int) -> bool:
        return self._click_button(x, y, self._generic_contact)

    def swipe(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float) -> bool:
        if self._controller is None:
            return False
        try:
            self._controller.post_swipe(
                start_x, start_y, end_x, end_y, int(duration * 1000)
            ).wait()
            return True
        except Exception:
            return False

    def release_all(self) -> bool:
        if self._controller is None:
            return False
        try:
            for contact in list(self._active_contacts.values()):
                self._controller.post_touch_up(contact).wait()
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

        if self._controller is None:
            return False

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
            self._controller.post_touch_move(x, y, contact, 1).wait()
        else:
            contact = self._get_contact("joystick_center")
            joystick_center_x, joystick_center_y = self._get_position("joystick_center", 198, 552)
            self._controller.post_touch_down(joystick_center_x, joystick_center_y, contact, 1).wait()
            time.sleep(JOYSTICK_TOUCHDOWN_DELAY)
            self._controller.post_touch_move(x, y, contact, 1).wait()
            self._active_contacts["joystick"] = contact

        if duration > 0:
            time.sleep(duration)
        return True

    def jump(self) -> bool:
        x, y = self._get_position("jump_button", 1166, 475)
        return self._click_button(x, y, self._get_contact("jump_button"))

    def dodge(self, direction: Optional[str] = None) -> bool:
        if self._controller is None:
            return False
        try:
            if direction:
                directions = self._get_joystick_directions()
                target = directions.get(direction)
                if target:
                    contact = self._get_contact("joystick_center")
                    joystick_center_x, joystick_center_y = self._get_position("joystick_center", 198, 552)
                    self._controller.post_touch_down(joystick_center_x, joystick_center_y, contact, 1).wait()
                    self._controller.post_touch_move(target[0], target[1], contact, 1).wait()
                    time.sleep(0.05)
                    x, y = self._get_position("sprint_button", 1166, 620)
                    sprint_contact = self._get_contact("sprint_button")
                    self._click_button(x, y, sprint_contact)
                    time.sleep(0.1)
                    self._controller.post_touch_up(contact).wait()
                    return True
                return False
            else:
                x, y = self._get_position("sprint_button", 1166, 620)
                return self._click_button(x, y, self._get_contact("sprint_button"))
        except Exception:
            return False

    def turn(self, angle: float) -> bool:
        if self._controller is None:
            return False
        try:
            dx = int(angle * 3.5)
            view_center_x, view_center_y = self._get_position("view_control_center", 1000, 150)
            contact = self._get_contact("view_control_center")
            self._controller.post_swipe(
                view_center_x, view_center_y,
                view_center_x + dx, view_center_y,
                TOUCH_SWIPE_DURATION_MS
            ).wait()
            return True
        except Exception:
            return False

    def interact(self, interaction_type: str) -> bool:
        x, y = self._get_position("interact_button", 1080, 390)
        return self._click_button(x, y, self._get_contact("interact_button"))

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
            if "joystick" in self._active_contacts and self._active_directions:
                x, y = self._calculate_joystick_position(self._active_directions)
                contact = self._active_contacts["joystick"]
                self._controller.post_touch_move(x, y, contact, 1).wait()
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
        if self._controller is None:
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
                        self._controller.post_touch_move(position[0], position[1], contact, 1).wait()
                    else:
                        # 没有方向了，归位摇杆
                        self._joystick_center()
                    return True
                else:
                    # 无方向参数或无 _active_directions：归位摇杆
                    return self._joystick_center()
            if action_name in self._active_contacts:
                contact = self._active_contacts[action_name]
                self._controller.post_touch_up(contact).wait()
                del self._active_contacts[action_name]
                return True
            return False
        except Exception:
            return False
