# -*- coding: utf-8 -*-
"""
类人化动作处理器，具有以下功能：
1. 随机反应延迟
2. 按键按下/释放时序模拟
3. 平滑移动路径生成（带加速度）
4. 随机位置偏移
5. 动作间隔模拟
6. 疲劳效果模拟
"""

import time
import random
import math
from typing import Dict, Any, Optional, List, Tuple, Callable


class Humanizer:
    """
    类人化动作处理器

    功能说明：
    1. 随机延迟
       - human_delay: 动作间隔延迟
       - reaction_delay: 反应时间延迟

    2. 按键时序
       - press_key_timing: 计算按键按下/保持/释放时序

    3. 平滑移动
       - smooth_move: 生成带加速度的移动路径

    4. 位置偏移
       - random_offset: 添加随机位置偏移

    5. 效果应用
       - apply_human_timing: 应用类人化时序到动作参数
       - simulate_fatigue: 模拟疲劳效果
       - get_natural_pause: 获取自然停顿时间

    参数配置（config/default.json）：
    {
        "humanization": {
            "enabled": true,
            "reaction_time_ms": {"min": 80, "max": 200},
            "key_press_time_ms": {"min": 50, "max": 120},
            "key_release_time_ms": {"min": 30, "max": 80},
            "action_gap_ms": {"min": 30, "max": 150},
            "mouse_speed": 300,
            "acceleration_factor": 0.15,
            "deceleration_factor": 0.15,
            "position_variance": 8,
            "jitter_amount": 2
        }
    }

    字段说明：
    - enabled: 是否启用类人化，默认 true
    - reaction_time_ms: 反应时间范围，默认 (80, 200) 毫秒
    - key_press_time_ms: 按键按下时间范围，默认 (50, 120) 毫秒
    - key_release_time_ms: 按键释放时间范围，默认 (30, 80) 毫秒
    - action_gap_ms: 动作间隔时间范围，默认 (30, 150) 毫秒
    - mouse_speed: 鼠标/触摸移动速度，默认 300 像素/秒
    - acceleration_factor: 加速阶段比例，默认 0.15
    - deceleration_factor: 减速阶段比例，默认 0.15
    - position_variance: 位置随机偏移范围，默认 8 像素
    - jitter_amount: 抖动幅度，默认 2 像素
    """

    def __init__(self):
        """
        初始化类人化处理器

        执行流程：
        1. 设置默认参数
        2. 初始化内部状态
        """
        # 类人化参数
        self.enabled = True

        # 反应时间范围（毫秒）
        self.reaction_time_ms: Tuple[int, int] = (80, 200)

        # 按键按下/释放时间范围（毫秒）
        self.key_press_time_ms: Tuple[int, int] = (50, 120)
        self.key_release_time_ms: Tuple[int, int] = (30, 80)

        # 动作间隔时间范围（毫秒）
        self.action_gap_ms: Tuple[int, int] = (30, 150)

        # 鼠标/触摸移动速度（像素/秒）
        self.mouse_speed: int = 300

        # 加速度曲线参数
        self.acceleration_factor: float = 0.15
        self.deceleration_factor: float = 0.15

        # 随机偏移范围（像素）
        self.position_variance: int = 8

        # 抖动幅度
        self.jitter_amount: int = 2

        # 最近动作时间（用于计算间隔）
        self._last_action_time: float = 0.0

    def human_delay(self, min_ms: Optional[int] = None, max_ms: Optional[int] = None) -> None:
        """
        添加类人随机延迟

        参数：
        - min_ms: 最小延迟时间，可选
        - max_ms: 最大延迟时间，可选

        执行流程：
        1. 检查是否启用类人化
        2. 计算随机延迟
        3. 执行延迟
        4. 记录最后动作时间
        """
        if not self.enabled:
            return

        min_val: int = min_ms if min_ms is not None else self.action_gap_ms[0]
        max_val: int = max_ms if max_ms is not None else self.action_gap_ms[1]

        delay = random.uniform(min_val, max_val) / 1000.0
        time.sleep(delay)
        self._last_action_time = time.time()

    def reaction_delay(self) -> None:
        """
        添加反应时间延迟（模拟真人反应）

        执行流程：
        1. 检查是否启用类人化
        2. 计算随机反应延迟
        3. 执行延迟
        """
        if not self.enabled:
            return

        delay = random.uniform(*self.reaction_time_ms) / 1000.0
        time.sleep(delay)

    def press_key_timing(self, key: str, duration: float) -> Dict[str, float]:
        """
        计算按键时序参数

        参数：
        - key: 按键名称
        - duration: 持续时间（秒）

        返回：
        - Dict[str, float]: 时序参数，包含：
          - press_delay: 按下延迟
          - hold_duration: 保持时间
          - release_delay: 释放延迟

        执行流程：
        1. 检查是否启用类人化
        2. 计算按下/释放延迟
        3. 计算实际保持时间
        4. 返回时序参数
        """
        if not self.enabled:
            return {
                'press_delay': 0,
                'hold_duration': duration,
                'release_delay': 0
            }

        press_delay = random.uniform(*self.key_press_time_ms) / 1000.0
        release_delay = random.uniform(*self.key_release_time_ms) / 1000.0

        # 计算实际保持时间（减去按下和释放时间）
        hold_duration = max(0.01, duration - press_delay - release_delay)

        return {
            'press_delay': press_delay,
            'hold_duration': hold_duration,
            'release_delay': release_delay
        }

    def smooth_move(self, start_x: int, start_y: int, end_x: int, end_y: int,
                    duration: Optional[float] = None) -> List[Tuple[int, int]]:
        """
        计算平滑移动路径（带加速度）

        参数：
        - start_x: 起始 X 坐标
        - start_y: 起始 Y 坐标
        - end_x: 结束 X 坐标
        - end_y: 结束 Y 坐标
        - duration: 持续时间，可选

        执行流程：
        1. 计算移动距离
        2. 计算持续时间（如果未提供）
        3. 生成带加速度的路径点
        4. 返回路径点列表
        """
        distance = math.hypot(end_x - start_x, end_y - start_y)

        # 计算持续时间
        if duration is None:
            duration = max(0.1, distance / self.mouse_speed)

        # 生成带加速度的路径点
        points: List[Tuple[int, int]] = []
        steps = int(duration * 60)  # 约60fps

        for i in range(steps + 1):
            t = i / steps

            # 应用加速度曲线（sigmoid曲线）
            if t < self.acceleration_factor:
                # 加速阶段
                t_accel = t / self.acceleration_factor
                eased_t = self._ease_in(t_accel)
            elif t > 1 - self.deceleration_factor:
                # 减速阶段
                t_decel = (t - (1 - self.deceleration_factor)) / self.deceleration_factor
                eased_t = 1 - self._ease_in(1 - t_decel)
            else:
                # 匀速阶段
                eased_t = (t - self.acceleration_factor) / (1 - self.acceleration_factor - self.deceleration_factor)

            # 计算当前位置
            x = start_x + (end_x - start_x) * eased_t
            y = start_y + (end_y - start_y) * eased_t

            # 添加微小抖动
            if self.jitter_amount > 0:
                x += random.uniform(-self.jitter_amount, self.jitter_amount)
                y += random.uniform(-self.jitter_amount, self.jitter_amount)

            points.append((int(x), int(y)))

        return points

    def _ease_in(self, t: float) -> float:
        """缓入曲线（quadratic）"""
        return t * t

    def _ease_out(self, t: float) -> float:
        """缓出曲线（quadratic）"""
        return 1 - (1 - t) * (1 - t)

    def _ease_in_out(self, t: float) -> float:
        """缓入缓出曲线"""
        return t * t * (3 - 2 * t)

    def random_offset(self, base_value: int, variance: Optional[int] = None) -> int:
        """
        获取带随机偏移的值

        参数：
        - base_value: 基础值
        - variance: 偏移范围，可选

        返回：
        - int: 偏移后的值
        """
        if not self.enabled:
            return base_value

        v: int = variance if variance is not None else self.position_variance
        return base_value + random.randint(-v, v)

    def apply_human_timing(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        应用类人化时序到动作参数

        参数：
        - params: 原始参数

        返回：
        - Dict[str, Any]: 处理后的参数

        执行流程：
        1. 复制原始参数
        2. 检查是否启用类人化
        3. 添加随机延迟
        4. 添加持续时间的微小变化
        5. 返回处理后的参数
        """
        result = params.copy()

        if not self.enabled:
            return result

        # 添加随机延迟
        if 'delay' not in params:
            result['human_delay'] = random.uniform(0.02, 0.08)

        # 添加持续时间的微小变化
        if 'duration' in params:
            duration = params['duration']
            if isinstance(duration, (int, float)):
                variation = duration * 0.1  # 最多10%的变化
                result['duration'] = duration + random.uniform(-variation, variation)

        return result

    def simulate_fatigue(self, action_count: int) -> float:
        """
        模拟疲劳效果（随着动作次数增加，反应变慢）

        参数：
        - action_count: 动作次数

        返回：
        - float: 疲劳因子（1.0 为正常，大于 1.0 表示疲劳）
        """
        if not self.enabled:
            return 1.0

        # 每10个动作增加10%的反应时间
        fatigue_factor = 1.0 + (action_count // 10) * 0.1
        return fatigue_factor

    def get_natural_pause(self) -> float:
        """
        获取自然停顿时间（模拟真人思考时间）

        返回：
        - float: 停顿时间（秒）
        """
        if not self.enabled:
            return 0.0

        # 随机决定是否需要停顿
        if random.random() < 0.3:  # 30%概率停顿
            return random.uniform(0.2, 0.5)
        return 0.0


class ActionSmoother:
    """
    动作平滑器

    功能说明：
    1. 平滑移动动作
    2. 执行组合动作
    """

    def __init__(self):
        """
        初始化动作平滑器

        执行流程：
        1. 初始化类人化处理器
        2. 初始化活跃动作集合
        3. 初始化动作历史记录
        """
        self._humanizer = Humanizer()
        self._active_actions: set = set()
        self._action_history: list = []

    def smooth_movement(self, direction: str, duration: float,
                       start_callback: Optional[Callable[[], None]] = None,
                       end_callback: Optional[Callable[[], None]] = None) -> None:
        """
        平滑的移动动作

        参数：
        - direction: 移动方向
        - duration: 持续时间
        - start_callback: 开始回调，可选
        - end_callback: 结束回调，可选

        执行流程：
        1. 记录动作历史
        2. 添加反应延迟
        3. 执行开始回调
        4. 执行移动动作
        5. 添加自然停顿
        6. 执行结束回调
        """
        # 记录动作历史
        self._action_history.append({
            'action': 'move',
            'direction': direction,
            'start_time': time.time(),
            'duration': duration
        })

        # 添加反应延迟
        self._humanizer.reaction_delay()

        # 开始回调
        if start_callback:
            start_callback()

        # 实际执行移动（带加速度效果）
        # 这里可以根据需要添加更复杂的物理模拟

        # 添加自然停顿
        pause = self._humanizer.get_natural_pause()
        if pause > 0:
            time.sleep(pause)

        # 结束回调
        if end_callback:
            end_callback()

    def execute_combo(self, combo_actions: List[Dict[str, Any]]) -> None:
        """
        执行组合动作（连贯的动作序列）

        参数：
        - combo_actions: 组合动作列表

        执行流程：
        1. 遍历动作列表
        2. 执行每个动作
        3. 添加动作间隔
        """
        for i, action_info in enumerate(combo_actions):
            action_name = action_info.get('action')
            params = action_info.get('params', {}) or {}
            delay = action_info.get('delay', 0)

            if action_name is None:
                continue

            # 执行动作
            self._execute_action(action_name, params)

            # 添加动作间隔（除了最后一个动作）
            if i < len(combo_actions) - 1:
                if isinstance(delay, (int, float)) and delay > 0:
                    time.sleep(delay / 1000.0)
                else:
                    self._humanizer.human_delay()

    def _execute_action(self, action_name: str, params: Dict[str, Any]) -> None:
        """
        执行单个动作

        参数：
        - action_name: 动作名称
        - params: 动作参数

        执行流程：
        1. 应用类人化效果
        2. 记录活跃动作
        3. 执行动作
        4. 移除活跃动作
        """
        # 应用类人化效果
        human_params = self._humanizer.apply_human_timing(params)

        # 记录活跃动作
        self._active_actions.add(action_name)

        try:
            # 这里应该调用实际的平台动作执行方法
            # 为了演示，我们只是记录动作
            print(f"Executing {action_name} with params: {human_params}")

            # 模拟动作执行时间
            duration = human_params.get('duration', 0)
            if isinstance(duration, (int, float)) and duration > 0:
                time.sleep(duration)
        finally:
            # 移除活跃动作
            self._active_actions.discard(action_name)

    def get_humanizer(self) -> Humanizer:
        """获取类人化处理器"""
        return self._humanizer


# 全局类人化处理器实例
humanizer = Humanizer()
action_smoother = ActionSmoother()
