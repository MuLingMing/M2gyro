# -*- coding: utf-8 -*-
"""
小地图自状态感知（第一档：只读自身状态，不做大地图定位）。

从 MaaEnd-2 cpp-algo MapAlgorithm.cpp 提炼的轻量实现：
- 圆形掩膜 + HSV 清洗（剔白色 UI 图标 / 彩色图标 / 未探索暗区）
- 玩家箭头：中心窗口内最大亮轮廓 → minEnclosingTriangle 取尖端 → atan2 朝向角
- 速度：清洗后小地图帧间相位相关（cv2.phaseCorrelate）求位移 → EMA 平滑
  （玩家箭头恒居中，不能用箭头位置差分；MaaEnd 的 MotionTracker 依赖
  大地图匹配位置，此处用相位相关替代）

朝向角约定与 geometry 一致：atan2(-dy, dx)，正上方（前向）= 90°。

依赖：cv2（.venv 已有 4.13.0），无新增依赖。
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np

from .geometry import angle_diff
from .params import NavigationParams


@dataclass
class MinimapObservation:
    """单帧小地图观测结果。"""

    heading_deg: Optional[float] = None
    heading_valid: bool = False
    speed_px_s: Optional[float] = None
    speed_valid: bool = False


class MinimapTracker:
    """小地图跟踪器（会话级实例，跨帧维护 EMA 与上一帧参考图）。

    参数示例（params 中 minimap 组）:
        enable_minimap=True, minimap_roi=(1040, 40, 200, 200),
        heading_ema_alpha=0.5, speed_ema_alpha=0.4
    """

    def __init__(self, params: NavigationParams) -> None:
        self._params = params
        self._heading_ema: Optional[float] = None
        self._speed_ema: Optional[float] = None
        self._last_gray: Optional[np.ndarray] = None
        self._last_t: Optional[float] = None

    def reset(self) -> None:
        """重置全部平滑状态（会话复位/切目标时调用）。"""
        self._heading_ema = None
        self._speed_ema = None
        self._last_gray = None
        self._last_t = None

    def update(self, image: np.ndarray) -> MinimapObservation:
        """处理一帧完整截图，输出朝向与速度观测。

        参数:
        - image: BGR 截图（MaaFW screencap 原始数组）

        返回值:
        - MinimapObservation（不可用时各 valid=False，不抛异常）
        """
        p = self._params
        if not p.enable_minimap:
            return MinimapObservation()
        mx, my, mw, mh = p.minimap_roi
        if mw <= 8 or mh <= 8 or image is None or image.size == 0:
            return MinimapObservation()
        if my + mh > image.shape[0] or mx + mw > image.shape[1]:
            return MinimapObservation()

        crop = np.ascontiguousarray(image[my : my + mh, mx : mx + mw])
        mask = self._build_clean_mask(crop)

        heading_obs = self._estimate_heading(crop, mask)
        speed_obs = self._estimate_speed(crop, mask)
        return MinimapObservation(
            heading_deg=heading_obs, heading_valid=heading_obs is not None,
            speed_px_s=speed_obs, speed_valid=speed_obs is not None,
        )

    # ===== 内部 =====

    def _build_clean_mask(self, crop: np.ndarray) -> np.ndarray:
        """构建有效区掩膜：圆形内，剔除白色 UI / 彩色图标 / 暗区。"""
        p = self._params
        h, w = crop.shape[:2]
        base = np.zeros((h, w), np.uint8)
        r = min(h, w) // 2 - p.minimap_border_margin
        if r <= 2:
            return base
        cv2.circle(base, (w // 2, h // 2), r, 255, -1)

        b, g, rr = crop[:, :, 0].astype(np.int16), crop[:, :, 1].astype(np.int16), crop[:, :, 2].astype(np.int16)
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        v, s = hsv[:, :, 2], hsv[:, :, 1]

        ui_mask = (v >= p.minimap_ui_v_min) & (s <= p.minimap_ui_s_max)
        icon_mask = (
            (rr > 100) & (g > 100) & (np.minimum(rr, g) - b > p.minimap_icon_diff_threshold)
        ) | ((b > 140) & (b > rr + 50))
        dark_mask = v <= p.minimap_dark_v_max

        keep = base > 0
        keep &= ~ui_mask
        keep &= ~icon_mask
        keep &= ~dark_mask
        out = np.where(keep, 255, 0).astype(np.uint8)
        # 轻度形态学去噪（抗锯齿残边）
        out = cv2.morphologyEx(out, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
        return out

    def _estimate_heading(
        self, crop: np.ndarray, mask: np.ndarray
    ) -> Optional[float]:
        """从清洗后中心窗口提取玩家箭头朝向角（度，EMA 平滑）。"""
        p = self._params
        h, w = crop.shape[:2]
        cx, cy = w // 2, h // 2
        r = min(h, w) // 2 - p.minimap_border_margin
        win = int(r * p.minimap_arrow_center_ratio)
        if win < 6:
            return self._heading_ema
        x0, y0 = max(0, cx - win), max(0, cy - win)
        roi_mask = mask[y0 : y0 + win * 2, x0 : x0 + win * 2]

        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        v = hsv[y0 : y0 + win * 2, x0 : x0 + win * 2, 2]
        bright = ((v >= p.minimap_arrow_v_min) & (roi_mask > 0)).astype(np.uint8) * 255

        contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return self._heading_ema
        contour = max(contours, key=cv2.contourArea)
        if cv2.contourArea(contour) < p.minimap_arrow_min_area:
            return self._heading_ema

        m = cv2.moments(contour)
        if m["m00"] <= 0:
            return self._heading_ema
        gx = m["m10"] / m["m00"] + x0
        gy = m["m01"] / m["m00"] + y0

        # 箭头尖端 = 轮廓上离质心最远的点
        # （minEnclosingTriangle 对等腰三角形返回的外接三角形顶点不含尖端，弃用）
        tip = max(
            ((float(pt[0][0]) + x0, float(pt[0][1]) + y0) for pt in contour),
            key=lambda q: math.hypot(q[0] - gx, q[1] - gy),
        )
        if math.hypot(tip[0] - gx, tip[1] - gy) < 2.0:
            return self._heading_ema
        heading = math.degrees(math.atan2(-(tip[1] - gy), tip[0] - gx))

        # 环绕感知下的 EMA 平滑
        if self._heading_ema is None:
            self._heading_ema = heading
        else:
            alpha = p.heading_ema_alpha
            self._heading_ema = self._heading_ema + alpha * angle_diff(
                heading, self._heading_ema
            )
            # 归一到 (-180, 180]
            if self._heading_ema > 180.0:
                self._heading_ema -= 360.0
            elif self._heading_ema <= -180.0:
                self._heading_ema += 360.0
        return self._heading_ema

    def _estimate_speed(
        self, crop: np.ndarray, mask: np.ndarray
    ) -> Optional[float]:
        """清洗后小地图帧间相位相关求位移速度（px/s，EMA 平滑）。

        玩家箭头恒居中，画面内容整体位移即玩家移动。
        """
        p = self._params
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY).astype(np.float32)
        gray = gray * (mask.astype(np.float32) / 255.0)
        now = time.monotonic()
        speed: Optional[float] = None
        if self._last_gray is not None and self._last_t is not None:
            dt = now - self._last_t
            if p.speed_min_dt_s <= dt <= p.speed_max_dt_s and dt > 1e-6:
                try:
                    (shift, _resp) = cv2.phaseCorrelate(self._last_gray, gray)
                    dx, dy = float(shift[0]), float(shift[1])
                    # 位移超过半径一半视为匹配失败（传送/切图）
                    max_shift = min(crop.shape[:2]) / 2.0
                    if math.hypot(dx, dy) <= max_shift:
                        inst = math.hypot(dx, dy) / dt
                        if self._speed_ema is None:
                            self._speed_ema = inst
                        else:
                            a = p.speed_ema_alpha
                            self._speed_ema = a * inst + (1 - a) * self._speed_ema
                        speed = self._speed_ema
                except cv2.error:
                    speed = None
        self._last_gray = gray
        self._last_t = now
        return speed
