# -*- coding: utf-8 -*-

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
from utils.logger import logger
import json
from typing import List, Dict, Any, Optional
from difflib import SequenceMatcher


@AgentServer.custom_action("MatchNoctoyagerTarget")
class MatchNoctoyagerTarget(CustomAction):
    """
    匹配夜航手册目标文字并点击"前往"按钮
    
    功能说明：
    1. 从 Custom Recognition 获取所有目标文字列表
    2. 检查目标文字是否在列表中（支持部分匹配）
    3. 如果找到，设置"前往"按钮的 ROI 并返回成功
    4. 如果未找到，执行滑动操作，然后重新扫描
    5. 设置最大滑动次数，防止死循环
    
    参数格式：
    {
        "target_text": "掠影 蒙恩的神甫",  // 必选，目标文字
        "scan_node": "扫描夜航手册目标",  // 可选，扫描节点名称，默认"扫描夜航手册目标"
        "swipe_node": "夜航手册等级滑动",  // 可选，滑动节点名称，默认"夜航手册等级滑动"
        "max_swipe_count": 10,  // 可选，最大滑动次数，默认10
        "similarity_threshold": 0.6,  // 可选，相似度阈值，默认0.6
        "go_button_roi_width": 120,  // 可选，"前往"按钮宽度，默认120
        "go_button_roi_height": 40,  // 可选，"前往"按钮高度，默认40
        "go_button_x_offset": 850  // 可选，"前往"按钮X坐标，默认850
    }
    """
    
    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        """
        执行目标匹配和点击逻辑
        
        参数:
        - context: 上下文对象
        - argv: 运行参数
        
        返回值:
        - CustomAction.RunResult: 执行结果
        """
        try:
            # 解析参数
            params = json.loads(argv.custom_action_param) if argv.custom_action_param else {}
            
            target_text = params.get("target_text", "")
            scan_node = params.get("scan_node", "扫描夜航手册目标")
            swipe_node = params.get("swipe_node", "夜航手册等级滑动")
            max_swipe_count = params.get("max_swipe_count", 10)
            similarity_threshold = params.get("similarity_threshold", 0.6)
            go_button_roi_width = params.get("go_button_roi_width", 120)
            go_button_roi_height = params.get("go_button_roi_height", 40)
            go_button_x_offset = params.get("go_button_x_offset", 850)
            
            if not target_text:
                logger.error("MatchNoctoyagerTarget: target_text 参数不能为空")
                return CustomAction.RunResult(success=False)
            
            # 获取当前节点的识别结果
            task_id = argv.task_detail.task_id
            task_detail = context.tasker.get_task_detail(task_id)
            
            if not task_detail or not task_detail.nodes:
                logger.error("MatchNoctoyagerTarget: 未找到任务详情")
                return CustomAction.RunResult(success=False)
            
            # 查找扫描节点的识别结果
            scan_result = None
            for node_detail in reversed(task_detail.nodes):
                if node_detail.name == scan_node:
                    if node_detail.recognition and node_detail.recognition.detail:
                        scan_result = node_detail.recognition.detail
                        break
            
            if not scan_result:
                logger.error(f"MatchNoctoyagerTarget: 未找到扫描节点 {scan_node} 的识别结果")
                return CustomAction.RunResult(success=False)
            
            # 解析扫描结果
            if isinstance(scan_result, str):
                scan_data = json.loads(scan_result)
            elif isinstance(scan_result, dict):
                scan_data = scan_result
            else:
                logger.error(f"MatchNoctoyagerTarget: 未知的扫描结果类型: {type(scan_result)}")
                return CustomAction.RunResult(success=False)
            
            targets = scan_data.get("targets", [])
            
            if not targets:
                logger.warning("MatchNoctoyagerTarget: 扫描结果中没有目标")
                return CustomAction.RunResult(success=False)
            
            # 匹配目标文字
            matched_target = self._match_target(targets, target_text, similarity_threshold)
            
            if matched_target:
                logger.info(f"MatchNoctoyagerTarget: 找到目标 '{matched_target['text']}'")
                
                # 设置"前往"按钮的 ROI
                kill_text_y = matched_target.get("kill_text_y", 0)
                go_button_roi = [
                    go_button_x_offset,
                    int(kill_text_y - go_button_roi_height / 2),
                    go_button_roi_width,
                    go_button_roi_height
                ]
                
                # 覆盖"前往"按钮的识别参数
                context.override_pipeline({
                    "点击前往按钮": {
                        "recognition": {
                            "type": "OCR",
                            "param": {
                                "expected": "前往",
                                "roi": go_button_roi,
                                "threshold": 0.3
                            }
                        }
                    }
                })
                
                logger.info(f"MatchNoctoyagerTarget: 设置'前往'按钮 ROI: {go_button_roi}")
                
                return CustomAction.RunResult(success=True)
            else:
                logger.info(f"MatchNoctoyagerTarget: 未找到目标 '{target_text}'")
                
                # 检查是否达到最大滑动次数
                swipe_count = self._get_swipe_count(context, argv.node_name)
                if swipe_count >= max_swipe_count:
                    logger.warning(f"MatchNoctoyagerTarget: 已达到最大滑动次数 {max_swipe_count}")
                    self._reset_swipe_count(context, argv.node_name)
                    return CustomAction.RunResult(success=False)
                
                # 执行滑动
                logger.info(f"MatchNoctoyagerTarget: 执行滑动 ({swipe_count + 1}/{max_swipe_count})")
                context.run_task(swipe_node)
                
                # 更新滑动次数
                self._update_swipe_count(context, argv.node_name, swipe_count + 1)
                
                # 重新扫描
                logger.info("MatchNoctoyagerTarget: 重新扫描目标")
                context.run_task(scan_node)
                
                # 递归调用自身（通过 override_next）
                context.override_next(argv.node_name, [argv.node_name])
                
                return CustomAction.RunResult(success=True)
            
        except Exception as e:
            logger.error(f"MatchNoctoyagerTarget 执行失败: {e}")
            return CustomAction.RunResult(success=False)
    
    def _match_target(
        self,
        targets: List[Dict[str, Any]],
        target_text: str,
        threshold: float
    ) -> Optional[Dict[str, Any]]:
        """
        匹配目标文字（支持部分匹配）
        
        参数:
        - targets: 目标列表
        - target_text: 目标文字
        - threshold: 相似度阈值
        
        返回值:
        - Optional[Dict]: 匹配到的目标，如果未找到则返回 None
        """
        for target in targets:
            text = target.get("text", "")
            
            # 完全匹配
            if target_text == text:
                return target
            
            # 部分匹配（目标文字包含在识别结果中）
            if target_text in text:
                return target
            
            # 相似度匹配
            similarity = SequenceMatcher(None, target_text, text).ratio()
            if similarity >= threshold:
                logger.info(f"MatchNoctoyagerTarget: 相似度匹配成功 (相似度: {similarity:.2f})")
                return target
        
        return None
    
    def _get_swipe_count(self, context: Context, node_name: str) -> int:
        """
        获取滑动次数
        
        参数:
        - context: 上下文对象
        - node_name: 节点名称
        
        返回值:
        - int: 滑动次数
        """
        # 使用节点数据存储滑动次数
        node_data = context.get_node_data(node_name)
        if node_data:
            return node_data.get("swipe_count", 0)
        return 0
    
    def _update_swipe_count(self, context: Context, node_name: str, count: int) -> None:
        """
        更新滑动次数
        
        参数:
        - context: 上下文对象
        - node_name: 节点名称
        - count: 滑动次数
        """
        # 使用节点数据存储滑动次数
        context.set_node_data(node_name, {"swipe_count": count})
    
    def _reset_swipe_count(self, context: Context, node_name: str) -> None:
        """
        重置滑动次数
        
        参数:
        - context: 上下文对象
        - node_name: 节点名称
        """
        # 使用节点数据存储滑动次数
        context.set_node_data(node_name, {"swipe_count": 0})


@AgentServer.custom_action("ClickNoctoyagerGoButton")
class ClickNoctoyagerGoButton(CustomAction):
    """
    点击夜航手册"前往"按钮
    
    功能说明：
    1. 识别"前往"按钮
    2. 点击按钮
    
    参数格式：
    {
        "expected": "前往",  // 可选，期望文字，默认"前往"
        "roi": [x, y, w, h],  // 可选，识别区域，默认全屏
        "threshold": 0.3  // 可选，识别阈值，默认0.3
    }
    """
    
    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        """
        执行点击"前往"按钮逻辑
        
        参数:
        - context: 上下文对象
        - argv: 运行参数
        
        返回值:
        - CustomAction.RunResult: 执行结果
        """
        try:
            # 解析参数
            params = json.loads(argv.custom_action_param) if argv.custom_action_param else {}
            
            expected = params.get("expected", "前往")
            roi = params.get("roi", [0, 0, 0, 0])
            threshold = params.get("threshold", 0.3)
            
            # 创建 OCR 节点配置
            ocr_node_name = "Noctoyager_Go_Button_OCR"
            ocr_config = {
                "recognition": {
                    "type": "OCR",
                    "param": {
                        "expected": expected,
                        "roi": roi,
                        "threshold": threshold
                    }
                },
                "action": {
                    "type": "Click",
                    "param": {
                        "target": True
                    }
                }
            }
            
            # 执行识别和点击
            context.override_pipeline({ocr_node_name: ocr_config})
            context.run_task(ocr_node_name)
            
            logger.info("ClickNoctoyagerGoButton: 已点击'前往'按钮")
            
            return CustomAction.RunResult(success=True)
            
        except Exception as e:
            logger.error(f"ClickNoctoyagerGoButton 执行失败: {e}")
            return CustomAction.RunResult(success=False)
