# -*- coding: utf-8 -*-

from maa.agent.agent_server import AgentServer
from maa.custom_recognition import CustomRecognition
from maa.context import Context
from utils.logger import logger
import json
from typing import List, Dict, Any, Optional, Tuple


@AgentServer.custom_recognition("ScanNoctoyagerTargets")
class ScanNoctoyagerTargets(CustomRecognition):
    """
    扫描夜航手册页面所有目标文字
    
    功能说明：
    1. 使用 OCR 识别整个页面的所有文字
    2. 找到所有"击杀可能获得"文字
    3. 提取每个"击杀可能获得"上方的目标文字
    4. 识别每个目标对应的"前往"按钮
    5. 匹配用户指定的目标物品
    6. 返回所有目标文字及其位置信息
    
    参数格式：
    {
        "roi": [x, y, w, h],  // 可选，指定识别区域，默认全屏
        "kill_text": "击杀可能获得",  // 可选，默认"击杀可能获得"
        "offset_y": -80,  // 可选，目标文字相对于"击杀可能获得"的Y偏移，默认-80
        "target_height": 60,  // 可选，目标文字区域高度，默认60
        "target_item": "",  // 可选，目标物品名称，为空时返回所有目标
        "goto_text": "前往",  // 可选，"前往"按钮文字，默认"前往"
        "goto_offset_y": 0,  // 可选，"前往"按钮相对于"击杀可能获得"的Y偏移，默认0
        "goto_width": 100  // 可选，"前往"按钮搜索宽度，默认100
    }
    
    返回格式：
    {
        "targets": [
            {
                "text": "掠影 蒙恩的神甫",
                "box": [x, y, w, h],
                "kill_text_y": 250,
                "goto_button": [x, y, w, h]  // 可选，"前往"按钮位置
            },
            ...
        ],
        "matched_target": {
            "text": "掠影 蒙恩的神甫",
            "box": [x, y, w, h],
            "kill_text_y": 250,
            "goto_button": [x, y, w, h]
        }  // 可选，匹配的目标
    }
    """
    
    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        """
        执行夜航手册目标扫描
        
        参数:
        - context: 上下文对象
        - argv: 分析参数
        
        返回值:
        - CustomRecognition.AnalyzeResult: 识别结果
        """
        try:
            # 解析参数
            params = json.loads(argv.custom_recognition_param) if argv.custom_recognition_param else {}
            
            roi = params.get("roi", [0, 0, 0, 0])  # 默认全屏
            kill_text = params.get("kill_text", "击杀可能获得")
            offset_y = params.get("offset_y", -80)
            target_height = params.get("target_height", 60)
            target_item = params.get("target_item", "")
            goto_text = params.get("goto_text", "前往")
            goto_offset_y = params.get("goto_offset_y", 0)
            goto_width = params.get("goto_width", 100)
            
            # 创建 OCR 节点配置
            ocr_node_name = "Noctoyager_OCR_Helper"
            ocr_config = {
                "recognition": {
                    "type": "OCR",
                    "param": {
                        "expected": [],  # 空数组表示识别所有文字
                        "roi": roi,
                        "threshold": 0.3,
                        "sort": "Horizontal"
                    }
                }
            }
            
            # 执行 OCR 识别
            context.override_pipeline({ocr_node_name: ocr_config})
            reco_detail = context.run_recognition(ocr_node_name, argv.image)
            
            if not reco_detail or not reco_detail.hit:
                logger.warning("ScanNoctoyagerTargets: OCR 未识别到任何文字")
                return CustomRecognition.AnalyzeResult(box=None, detail={"targets": []})
            
            # 获取所有 OCR 识别结果
            all_texts = self._parse_ocr_results(reco_detail.raw_detail)
            
            if not all_texts:
                logger.warning("ScanNoctoyagerTargets: 未解析到任何文字")
                return CustomRecognition.AnalyzeResult(box=None, detail={"targets": []})
            
            # 找到所有"击杀可能获得"文字
            kill_texts = self._find_kill_texts(all_texts, kill_text)
            
            if not kill_texts:
                logger.warning(f"ScanNoctoyagerTargets: 未找到 '{kill_text}' 文字")
                return CustomRecognition.AnalyzeResult(box=None, detail={"targets": []})
            
            # 提取每个"击杀可能获得"上方的目标文字和"前往"按钮
            targets = self._extract_targets(
                all_texts, 
                kill_texts, 
                offset_y, 
                target_height, 
                goto_text, 
                goto_offset_y, 
                goto_width
            )
            
            # 匹配目标物品
            matched_target = None
            if target_item:
                matched_target = self._match_target(targets, target_item)
                if matched_target:
                    logger.info(f"ScanNoctoyagerTargets: 匹配到目标物品 '{target_item}'")
                else:
                    logger.warning(f"ScanNoctoyagerTargets: 未匹配到目标物品 '{target_item}'")
            
            logger.info(f"ScanNoctoyagerTargets: 找到 {len(targets)} 个目标")
            
            result_detail = {"targets": targets}
            if matched_target:
                result_detail["matched_target"] = matched_target
            
            # 如果匹配到目标，返回目标的位置
            if matched_target:
                target_box = matched_target.get("box", [0, 0, 0, 0])
                return CustomRecognition.AnalyzeResult(
                    box=(target_box[0], target_box[1], target_box[2], target_box[3]),
                    detail=result_detail
                )
            else:
                return CustomRecognition.AnalyzeResult(
                    box=(0, 0, 1080, 720),  # 返回全屏区域
                    detail=result_detail
                )
            
        except Exception as e:
            logger.error(f"ScanNoctoyagerTargets 执行失败: {e}")
            return CustomRecognition.AnalyzeResult(box=None, detail={"targets": []})
    
    def _parse_ocr_results(self, raw_detail: Any) -> List[Dict[str, Any]]:
        """
        解析 OCR 原始结果
        
        参数:
        - raw_detail: OCR 原始结果
        
        返回值:
        - List[Dict]: 文字列表，每个元素包含 text 和 box
        """
        try:
            if not raw_detail:
                return []
            
            # 尝试解析 raw_detail
            if isinstance(raw_detail, str):
                detail_data = json.loads(raw_detail)
            elif isinstance(raw_detail, dict):
                detail_data = raw_detail
            else:
                logger.warning(f"未知的 raw_detail 类型: {type(raw_detail)}")
                return []
            
            # 提取所有识别结果
            all_texts = []
            
            # 检查是否有 all_results 字段
            if "all_results" in detail_data:
                for result in detail_data["all_results"]:
                    text = result.get("text", "")
                    box = result.get("box", [])
                    if text and box:
                        all_texts.append({
                            "text": text,
                            "box": box
                        })
            # 检查是否有 best_result 字段
            elif "best_result" in detail_data:
                result = detail_data["best_result"]
                text = result.get("text", "")
                box = result.get("box", [])
                if text and box:
                    all_texts.append({
                        "text": text,
                        "box": box
                    })
            else:
                logger.warning(f"未知的 detail_data 结构: {detail_data.keys()}")
            
            return all_texts
            
        except Exception as e:
            logger.error(f"解析 OCR 结果失败: {e}")
            return []
    
    def _find_kill_texts(self, all_texts: List[Dict[str, Any]], kill_text: str) -> List[Dict[str, Any]]:
        """
        找到所有"击杀可能获得"文字
        
        参数:
        - all_texts: 所有识别到的文字
        - kill_text: 要查找的文字
        
        返回值:
        - List[Dict]: 匹配的文字列表
        """
        kill_texts = []
        for text_info in all_texts:
            text = text_info.get("text", "")
            if kill_text in text:
                kill_texts.append(text_info)
        
        return kill_texts
    
    def _extract_targets(
        self,
        all_texts: List[Dict[str, Any]],
        kill_texts: List[Dict[str, Any]],
        offset_y: int,
        target_height: int,
        goto_text: str,
        goto_offset_y: int,
        goto_width: int
    ) -> List[Dict[str, Any]]:
        """
        提取每个"击杀可能获得"上方的目标文字和"前往"按钮
        
        参数:
        - all_texts: 所有识别到的文字
        - kill_texts: 所有"击杀可能获得"文字
        - offset_y: Y 偏移
        - target_height: 目标区域高度
        - goto_text: "前往"按钮文字
        - goto_offset_y: "前往"按钮 Y 偏移
        - goto_width: "前往"按钮搜索宽度
        
        返回值:
        - List[Dict]: 目标文字列表
        """
        targets = []
        
        for kill_text_info in kill_texts:
            kill_box = kill_text_info.get("box", [])
            if not kill_box or len(kill_box) < 4:
                continue
            
            # 获取"击杀可能获得"的位置
            kill_x, kill_y, kill_w, kill_h = kill_box[:4]
            kill_center_y = kill_y + kill_h / 2
            
            # 计算目标文字区域的 Y 范围
            target_y_min = kill_center_y + offset_y - target_height / 2
            target_y_max = kill_center_y + offset_y + target_height / 2
            
            # 找到在该区域内的文字
            target_texts = []
            for text_info in all_texts:
                text_box = text_info.get("box", [])
                if not text_box or len(text_box) < 4:
                    continue
                
                text_x, text_y, text_w, text_h = text_box[:4]
                text_center_y = text_y + text_h / 2
                
                # 检查文字是否在目标区域内
                if target_y_min <= text_center_y <= target_y_max:
                    # 排除"击杀可能获得"本身
                    if text_info not in kill_texts:
                        target_texts.append(text_info)
            
            # 合并同一行的文字
            target_info = None
            if target_texts:
                merged_text = self._merge_texts_on_same_line(target_texts)
                if merged_text:
                    target_info = {
                        "text": merged_text["text"],
                        "box": merged_text["box"],
                        "kill_text_y": kill_center_y
                    }
            
            # 识别"前往"按钮
            if target_info:
                goto_button = self._find_goto_button(
                    all_texts, 
                    kill_x, 
                    kill_center_y, 
                    goto_text, 
                    goto_offset_y, 
                    goto_width
                )
                if goto_button:
                    target_info["goto_button"] = goto_button
                
                targets.append(target_info)
        
        return targets
    
    def _find_goto_button(
        self,
        all_texts: List[Dict[str, Any]],
        kill_x: float,
        kill_center_y: float,
        goto_text: str,
        goto_offset_y: int,
        goto_width: int
    ) -> Optional[List[float]]:
        """
        找到"前往"按钮
        
        参数:
        - all_texts: 所有识别到的文字
        - kill_x: "击杀可能获得"的 X 坐标
        - kill_center_y: "击杀可能获得"的 Y 中心坐标
        - goto_text: "前往"按钮文字
        - goto_offset_y: "前往"按钮 Y 偏移
        - goto_width: "前往"按钮搜索宽度
        
        返回值:
        - List[float]: "前往"按钮的位置 [x, y, w, h]
        """
        # 计算"前往"按钮的搜索区域
        goto_y_min = kill_center_y + goto_offset_y - 30
        goto_y_max = kill_center_y + goto_offset_y + 30
        goto_x_min = kill_x + 200  # 假设"前往"按钮在"击杀可能获得"右侧
        goto_x_max = goto_x_min + goto_width
        
        for text_info in all_texts:
            text = text_info.get("text", "")
            if goto_text in text:
                text_box = text_info.get("box", [])
                if not text_box or len(text_box) < 4:
                    continue
                
                text_x, text_y, text_w, text_h = text_box[:4]
                text_center_x = text_x + text_w / 2
                text_center_y = text_y + text_h / 2
                
                # 检查是否在搜索区域内
                if (goto_x_min <= text_center_x <= goto_x_max and
                    goto_y_min <= text_center_y <= goto_y_max):
                    return text_box
        
        return None
    
    def _match_target(self, targets: List[Dict[str, Any]], target_item: str) -> Optional[Dict[str, Any]]:
        """
        匹配目标物品
        
        参数:
        - targets: 目标文字列表
        - target_item: 目标物品名称
        
        返回值:
        - Dict: 匹配的目标信息
        """
        for target in targets:
            target_text = target.get("text", "")
            # 模糊匹配
            if target_item in target_text or target_text in target_item:
                return target
        
        return None
    
    def _merge_texts_on_same_line(self, texts: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        合并同一行的文字
        
        参数:
        - texts: 同一行的文字列表
        
        返回值:
        - Dict: 合并后的文字信息
        """
        if not texts:
            return None
        
        if len(texts) == 1:
            return texts[0]
        
        # 按 X 坐标排序
        sorted_texts = sorted(texts, key=lambda t: t.get("box", [0])[0])
        
        # 合并文字
        merged_text = " ".join([t.get("text", "") for t in sorted_texts])
        
        # 计算合并后的 box
        min_x = min([t.get("box", [0])[0] for t in sorted_texts])
        min_y = min([t.get("box", [0, 0, 0, 0])[1] for t in sorted_texts if len(t.get("box", [])) >= 4])
        max_x = max([t.get("box", [0, 0, 0, 0])[0] + t.get("box", [0, 0, 0, 0])[2] for t in sorted_texts if len(t.get("box", [])) >= 4])
        max_y = max([t.get("box", [0, 0, 0, 0])[1] + t.get("box", [0, 0, 0, 0])[3] for t in sorted_texts if len(t.get("box", [])) >= 4])
        
        return {
            "text": merged_text,
            "box": [min_x, min_y, max_x - min_x, max_y - min_y]
        }
