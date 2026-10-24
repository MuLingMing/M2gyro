# -*- coding: utf-8 -*-
"""
感知层：屏幕目标收集（模板匹配）与距离提取（OCR）。

从旧 PathFindingReco._collect_targets/_match_template/_extract_distance 移植，
并修复：_extract_distance 的 ROI 只对 x/y 做 max(0,..)，宽高未裁剪到屏幕内。
"""

from __future__ import annotations

import functools
import os
import re
from typing import List, Optional, Tuple

import numpy as np
from maa.context import Context
from maa.define import OCRResult, RectType, TemplateMatchResult
from maa.pipeline import JOCR, JRecognitionType, JTemplateMatch

from utils.logger import logger

from ..selector import TargetInfo
from .geometry import (
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TURN_CLIP_HORIZONTAL,
    TURN_CLIP_VERTICAL,
)
from .params import NavigationParams

# 转向条带常量已迁移至 geometry.py（policy 纯函数层亦引用），此处再导出保持兼容。
__all__ = [
    "TURN_CLIP_HORIZONTAL",
    "TURN_CLIP_VERTICAL",
    "ScreenPerceiver",
]


@functools.lru_cache(maxsize=64)
def _expand_folder_cached(image_dir: str, folder_path: str) -> Optional[List[str]]:
    """缓存的目标文件夹展开（image_dir 作为缓存键第一维）。"""
    image_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
    files: List[str] = []
    for root, _, filenames in os.walk(folder_path):
        for filename in filenames:
            if os.path.splitext(filename.lower())[1] not in image_extensions:
                continue
            full_path = os.path.join(root, filename)
            rel_path = os.path.relpath(full_path, image_dir)
            files.append(rel_path.replace("\\", "/"))
    if not files:
        return None
    return sorted(files)


class ScreenPerceiver:
    """屏幕感知器：模板匹配收集目标 + OCR 提取距离。

    参数:
    - context: MaaFW Context（用于 run_recognition_direct）
    """

    def __init__(self, context: Context) -> None:
        self._context = context

    # ===== 模板匹配 =====

    def collect_targets(
        self,
        img: np.ndarray,
        params: NavigationParams,
        roi: Optional[Tuple[int, int, int, int]] = None,
    ) -> List[TargetInfo]:
        """收集所有匹配目标（不含距离）。priority 模式命中首个模板即止。"""
        use_roi = roi if roi is not None else params.roi
        targets: List[TargetInfo] = []
        for template_name in params.expected_templates:
            matched = self.match_template(img, template_name, use_roi, params.threshold)
            if matched:
                targets.extend(matched)
                if params.selector_type == "priority":
                    break
        return targets

    def match_template(
        self,
        img: np.ndarray,
        template_name: str,
        roi: Tuple[int, int, int, int],
        threshold: float,
    ) -> List[TargetInfo]:
        """单模板匹配（template_name 为文件夹时自动展开）。"""
        templates = self._expand_template_folder(template_name)
        if templates is None:
            templates = [template_name]
        if not templates:
            return []

        reco_param = JTemplateMatch(
            template=templates,
            roi=roi,
            threshold=[threshold] * len(templates),
            green_mask=True,
        )
        reco_detail = self._context.run_recognition_direct(
            JRecognitionType.TemplateMatch, reco_param, img
        )

        targets: List[TargetInfo] = []
        if reco_detail is not None and reco_detail.hit:
            results = (
                reco_detail.filtered_results
                if reco_detail.filtered_results
                else reco_detail.all_results
            )
            for result in results:
                if not isinstance(result, TemplateMatchResult):
                    continue
                if result.score < threshold:
                    continue
                box = result.box
                if box is None:
                    continue
                if isinstance(box, (list, tuple)):
                    x, y, w, h = box[0], box[1], box[2], box[3]
                else:
                    x, y, w, h = box.x, box.y, box.w, box.h
                center = (x + w / 2, y + h / 2)
                targets.append(
                    TargetInfo(
                        template=template_name,
                        center=center,
                        bbox=(x, y, w, h),
                        score=result.score,
                    )
                )
        return targets

    # ===== 距离提取 =====

    def extract_distance(
        self,
        img: np.ndarray,
        target: TargetInfo,
        params: NavigationParams,
    ) -> TargetInfo:
        """提取目标下方距离文本（OCR），失败时原样返回（distance 保持 None）。"""
        x, y, w, h = target.bbox
        offset_x, offset_y, offset_w, offset_h = params.distance_offset
        raw_x = x + offset_x
        raw_y = y + offset_y
        # 修复旧版 bug：x/y 需钳到屏幕内，且宽高需按左侧裁剪量收缩
        roi_x = max(0, raw_x)
        roi_y = max(0, raw_y)
        roi_w = max(1, w + offset_w - (roi_x - raw_x))
        roi_h = max(1, h + offset_h - (roi_y - raw_y))
        roi = (roi_x, roi_y, roi_w, roi_h)

        try:
            reco_param = JOCR(
                expected=[params.distance_pattern],
                roi=roi,
                threshold=params.distance_threshold,
            )
            reco_detail = self._context.run_recognition_direct(
                JRecognitionType.OCR, reco_param, img
            )
            if reco_detail is not None and reco_detail.hit:
                best = reco_detail.best_result
                if isinstance(best, OCRResult) and best.text:
                    match = re.search(params.distance_pattern, best.text)
                    if match and match.group(1).isdigit():
                        return TargetInfo(
                            template=target.template,
                            center=target.center,
                            bbox=target.bbox,
                            score=target.score,
                            distance=int(match.group(1)),
                        )
        except Exception as e:
            logger.warning(
                "[ScreenPerceiver] distance extraction failed for %s roi=%s: %s",
                target.template,
                roi,
                e,
            )
        return target

    # ===== 资源目录 =====

    @staticmethod
    def _resolve_image_dir() -> Optional[str]:
        """解析资源图片目录（源码路径优先，回退 CWD）。"""
        candidates = [
            os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "assets", "resource", "image")
            ),
            os.path.abspath(os.path.join(os.getcwd(), "assets", "resource", "image")),
        ]
        for path in candidates:
            if os.path.isdir(path):
                return path
        return None

    def _expand_template_folder(self, template_name: str) -> Optional[List[str]]:
        """若 template_name 对应文件夹则展开为其中所有图片相对路径。"""
        image_dir = self._resolve_image_dir()
        if image_dir is None:
            return None
        folder_path = os.path.join(image_dir, template_name)
        if not os.path.isdir(folder_path):
            return None
        return _expand_folder_cached(image_dir, folder_path)
