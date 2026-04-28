import time
from typing import Optional, Tuple, Dict, Any, Union
from maa.controller import Controller
from maa.context import Context
from ..base import PlatformBase
from ...config import ConfigManager


TOUCH_SWIPE_DURATION_MS = 70


class AdbPlatform(PlatformBase):
    """ADB平台实现，优先使用 config/default.json 中的配置"""

    def __init__(self, platform_context: Controller):
        super().__init__(platform_context)
        self._controller_type = "adb"
        self._controller = None

        if isinstance(platform_context, Controller):
            self._controller = platform_context
        elif isinstance(platform_context, Context) and hasattr(platform_context, "tasker"):
            self._controller = platform_context.tasker.controller

        self._config_manager = ConfigManager()
        self._touch_positions = self._load_touch_positions()
        self._generic_contact = self._load_generic_contact()
        self._active_contacts: Dict[str, int] = {}

    def _load_touch_positions(self) -> Dict[str, Any]:
        """从配置文件加载触摸位置配置"""
        adb_config = self._config_manager.get("platforms.adb", {})
        return adb_config.get("touch_positions", {})

    def _load_generic_contact(self) -> int:
        """从配置文件加载通用触点ID"""
        adb_config = self._config_manager.get("platforms.adb", {})
        return adb_config.get("generic_contact", 8)

    def _get_position(self, position_name: str, default_x: int, default_y: int) -> Tuple[int, int]:
        """获取按钮位置"""
        position = self._touch_positions.get(position_name, {})
        x = position.get("x", default_x)
        y = position.get("y", default_y)
        return (x, y)

    def _get_contact(self, position_name: str) -> int:
        """获取按钮对应的触点ID"""
        position_config = self._touch_positions.get(position_name, {})
        return position_config.get("contact", self._generic_contact)

    def move(self, direction: str, duration: float) -> bool:
        """移动
        如果 duration <= 0，表示只按下不松开（由时间线系统管理）
        如果 duration > 0，表示完整的按下-等待-松开
        """
        if direction == "center":
            return self._joystick_center()

        joystick_center_x, joystick_center_y = self._get_position("joystick_center", 198, 552)
        joystick_config = self._touch_positions.get("joystick_center", {})
        joystick_run_offset = joystick_config.get("joystick_run_offset", -72)

        direction_map = {
            "forward": (joystick_center_x, joystick_center_y + joystick_run_offset),
            "backward": (joystick_center_x, joystick_center_y - joystick_run_offset),
            "left": (joystick_center_x - 72, joystick_center_y),
            "right": (joystick_center_x + 72, joystick_center_y)
        }
        target = direction_map.get(direction)
        if not target:
            return False
        return self._joystick_move(target[0], target[1], duration)

    def _joystick_center(self) -> bool:
        """摇杆回到中心（松开）"""
        try:
            contact = self._get_contact("joystick_center")
            if "joystick" in self._active_contacts and self._controller:
                self._controller.post_touch_up(contact).wait()
                del self._active_contacts["joystick"]
            return True
        except Exception:
            return False

    def _joystick_move(self, x: int, y: int, duration: float) -> bool:
        """摇杆移动
        1. 先在中心按下
        2. 滑动到目标位置
        3. 在目标位置保持按下
        4. 如果 duration > 0，等待后松开
        """
        try:
            if not self._controller:
                return False

            contact = self._get_contact("joystick_center")
            joystick_center_x, joystick_center_y = self._get_position("joystick_center", 198, 552)
            
            x = max(0, min(x, 1279))
            y = max(0, min(y, 719))
            
            self._controller.post_touch_move(joystick_center_x, joystick_center_y, contact, 0).wait()
            self._controller.post_touch_down(joystick_center_x, joystick_center_y, contact, 0).wait()
            self._controller.post_touch_move(x, y, contact, 0).wait()
            
            self._active_contacts["joystick"] = contact

            if duration > 0:
                time.sleep(duration)
                self._controller.post_touch_up(contact).wait()
                if "joystick" in self._active_contacts:
                    del self._active_contacts["joystick"]
            
            return True
        except Exception:
            return False

    def jump(self) -> bool:
        """跳跃（瞬时动作）"""
        x, y = self._get_position("jump_button", 1166, 475)
        return self._click_button(x, y, self._get_contact("jump_button"))

    def dodge(self, direction: Optional[str] = None) -> bool:
        """闪避/冲刺（瞬时动作）"""
        x, y = self._get_position("sprint_button", 1166, 620)
        return self._click_button(x, y, self._get_contact("sprint_button"))

    def turn(self, angle: float) -> bool:
        """转向（瞬时滑动动作）"""
        try:
            if not self._controller:
                return False

            dx = int(angle * 3.5)
            view_center_x, view_center_y = self._get_position("view_control_center", 1000, 150)
            contact = self._get_contact("view_control_center")
            self._controller.post_swipe(
                view_center_x,
                view_center_y,
                view_center_x + dx,
                view_center_y,
                TOUCH_SWIPE_DURATION_MS
            ).wait()
            return True
        except Exception:
            return False

    def interact(self, interaction_type: str) -> bool:
        """交互（瞬时动作）"""
        x, y = self._get_position("interact_button", 1080, 390)
        return self._click_button(x, y, self._get_contact("interact_button"))

    def spiral_leap(self) -> bool:
        """螺旋飞跃（瞬时动作）"""
        x, y = self._get_position("spiral_leap_button", 1166, 475)
        return self._click_button(x, y, self._get_contact("spiral_leap_button"))

    def crouch(self) -> bool:
        """下蹲（瞬时动作）"""
        x, y = self._get_position("crouch_button", 1166, 620)
        return self._click_button(x, y, self._get_contact("crouch_button"))

    def charge_attack(self, duration: float, x: Optional[int] = None, y: Optional[int] = None) -> bool:
        """蓄力攻击
        duration > 0: 完整的按下-等待-松开
        duration <= 0: 只按下，不松开（由时间线系统管理）
        """
        try:
            if not self._controller:
                return False

            charge_attack_x, charge_attack_y = self._get_position("charge_attack_button", 1030, 551)
            x = x if x is not None else charge_attack_x
            y = y if y is not None else charge_attack_y

            x = max(0, min(x, 1279))
            y = max(0, min(y, 719))

            contact = self._get_contact("charge_attack_button")
            self._controller.post_touch_move(x, y, contact, 0).wait()
            self._controller.post_touch_down(x, y, contact, 0).wait()
            
            self._active_contacts["charge_attack"] = contact

            if duration > 0:
                time.sleep(duration)
                self._controller.post_touch_up(contact).wait()
                if "charge_attack" in self._active_contacts:
                    del self._active_contacts["charge_attack"]
            
            return True
        except Exception:
            return False

    def _click_button(self, x: int, y: int, contact: int = 8) -> bool:
        """点击按钮（瞬时动作）
        完整执行：按下-等待-松开
        """
        try:
            if not self._controller:
                return False

            x = max(0, min(x, 1279))
            y = max(0, min(y, 719))
            self._controller.post_touch_move(x, y, contact, 0).wait()
            self._controller.post_touch_down(x, y, contact, 0).wait()
            time.sleep(0.05)
            self._controller.post_touch_up(contact).wait()
            return True
        except Exception:
            return False

    def press_key(self, key: str, duration: float) -> bool:
        """按键（兼容旧系统）"""
        joystick_center_x, joystick_center_y = self._get_position("joystick_center", 198, 552)
        joystick_config = self._touch_positions.get("joystick_center", {})
        joystick_run_offset = joystick_config.get("joystick_run_offset", -72)
        jump_x, jump_y = self._get_position("jump_button", 1166, 475)
        interact_x, interact_y = self._get_position("interact_button", 1080, 390)
        sprint_x, sprint_y = self._get_position("sprint_button", 1166, 620)
        charge_x, charge_y = self._get_position("charge_attack_button", 1030, 551)

        key_positions = {
            "W": (joystick_center_x, joystick_center_y + joystick_run_offset),
            "A": (joystick_center_x - 72, joystick_center_y),
            "S": (joystick_center_x, joystick_center_y - joystick_run_offset),
            "D": (joystick_center_x + 72, joystick_center_y),
            "Space": (jump_x, jump_y),
            "F": (interact_x, interact_y),
            "Shift": (sprint_x, sprint_y),
            "Q": (jump_x, jump_y),
            "C": (charge_x, charge_y)
        }

        target = key_positions.get(key)
        if target:
            if key in ["W", "A", "S", "D"]:
                return self._joystick_move(target[0], target[1], duration)
            else:
                return self._click_button(target[0], target[1], self._get_contact("jump_button" if key in ["Space", "Q"] else "sprint_button" if key == "Shift" else "interact_button" if key == "F" else "charge_attack_button"))
        return False

    def release_key(self, key: str) -> bool:
        """释放键位（兼容旧系统）"""
        try:
            if not self._controller:
                return False

            contact = self._get_contact("joystick_center")
            self._controller.post_touch_up(contact).wait()
            return True
        except Exception:
            return False

    def click(self, x: int, y: int) -> bool:
        """点击（瞬时动作）"""
        return self._click_button(x, y, self._generic_contact)

    def swipe(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float) -> bool:
        """滑动（瞬时动作）"""
        try:
            if not self._controller:
                return False

            self._controller.post_swipe(
                start_x,
                start_y,
                end_x,
                end_y,
                int(duration * 1000)
            ).wait()
            return True
        except Exception:
            return False

    def release_joystick(self):
        """释放摇杆（供时间线系统调用）"""
        return self._joystick_center()

    def release_charge_attack(self):
        """释放蓄力攻击（供时间线系统调用）"""
        try:
            if not self._controller:
                return False

            if "charge_attack" in self._active_contacts:
                contact = self._active_contacts["charge_attack"]
                self._controller.post_touch_up(contact).wait()
                del self._active_contacts["charge_attack"]
            return True
        except Exception:
            return False

    def release_all(self) -> bool:
        """释放所有按键"""
        try:
            if not self._controller:
                return False

            for contact in list(self._active_contacts.values()):
                self._controller.post_touch_up(contact).wait()
            self._active_contacts.clear()
            return True
        except Exception:
            return False
