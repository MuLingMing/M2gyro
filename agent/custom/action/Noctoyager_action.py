# -*- coding: utf-8 -*-

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context
from utils.logger import logger
import json
from typing import Dict, Any, Optional


@AgentServer.custom_action("NoctoyagerAction")
def NoctoyagerAction(
    context: Context,
    argv: CustomAction.Arg
) -> CustomAction.Result:
    """
    夜航手册自定义动作
    
    功能说明：
    1. 执行滑动操作，寻找目标物品
    2. 点击"前往"按钮
    3. 处理活动期间的逻辑
    
    参数格式：
    {
        "action_type": "swipe",  // 动作类型：swipe（滑动）或 click（点击）
        "swipe_type": "up",  // 滑动类型：up（上滑）或 down（下滑）
        "swipe_coords": [[800, 444], [800, 229]],  // 滑动坐标
        "swipe_duration": 500,  // 滑动持续时间（毫秒）
        "click_target": "goto",  // 点击目标：goto（前往按钮）或 target（目标物品）
        "target_item": "",  // 目标物品名称
        "max_swipe_count": 10,  // 最大滑动次数
        "current_swipe_count": 0  // 当前滑动次数
    }
    
    返回格式：
    {
        "success": true,  // 执行是否成功
        "message": "执行成功",  // 执行结果消息
        "swipe_count": 0,  // 执行的滑动次数
        "found_target": false  // 是否找到目标
    }
    """
    try:
        # 解析参数
        params = json.loads(argv.custom_action_param) if argv.custom_action_param else {}
        
        action_type = params.get("action_type", "swipe")
        swipe_type = params.get("swipe_type", "up")
        swipe_coords = params.get("swipe_coords", [[800, 444], [800, 229]])
        swipe_duration = params.get("swipe_duration", 500)
        click_target = params.get("click_target", "goto")
        target_item = params.get("target_item", "")
        max_swipe_count = params.get("max_swipe_count", 10)
        current_swipe_count = params.get("current_swipe_count", 0)
        
        result = {
            "success": False,
            "message": "",
            "swipe_count": current_swipe_count,
            "found_target": False
        }
        
        if action_type == "swipe":
            # 执行滑动操作
            if current_swipe_count >= max_swipe_count:
                result["message"] = f"达到最大滑动次数 {max_swipe_count}"
                return CustomAction.Result(json.dumps(result))
            
            # 执行滑动
            swipe_node_name = "Noctoyager_Swipe"
            swipe_config = {
                "action": {
                    "type": "Swipe",
                    "param": {
                        "start": swipe_coords[0],
                        "end": swipe_coords[1],
                        "duration": swipe_duration
                    }
                }
            }
            
            context.override_pipeline({swipe_node_name: swipe_config})
            action_result = context.run_action(swipe_node_name, argv.image)
            
            if action_result and action_result.success:
                current_swipe_count += 1
                result["success"] = True
                result["message"] = f"执行{swipe_type}滑动成功"
                result["swipe_count"] = current_swipe_count
            else:
                result["message"] = "滑动执行失败"
                
        elif action_type == "click":
            # 执行点击操作
            if not argv.recognition_result or not argv.recognition_result.detail:
                result["message"] = "没有识别结果"
                return CustomAction.Result(json.dumps(result))
            
            # 解析识别结果
            try:
                recognition_detail = json.loads(argv.recognition_result.detail)
            except Exception as e:
                logger.error(f"解析识别结果失败: {e}")
                result["message"] = "解析识别结果失败"
                return CustomAction.Result(json.dumps(result))
            
            # 找到匹配的目标
            matched_target = recognition_detail.get("matched_target")
            if not matched_target:
                result["message"] = "未找到匹配的目标"
                return CustomAction.Result(json.dumps(result))
            
            # 确定点击位置
            click_position = None
            if click_target == "goto":
                # 点击"前往"按钮
                goto_button = matched_target.get("goto_button")
                if not goto_button:
                    result["message"] = "未找到"前往"按钮"
                    return CustomAction.Result(json.dumps(result))
                # 计算"前往"按钮的中心点
                x, y, w, h = goto_button
                click_position = [x + w/2, y + h/2]
            elif click_target == "target":
                # 点击目标物品
                target_box = matched_target.get("box")
                if not target_box:
                    result["message"] = "未找到目标物品位置"
                    return CustomAction.Result(json.dumps(result))
                # 计算目标物品的中心点
                x, y, w, h = target_box
                click_position = [x + w/2, y + h/2]
            
            if click_position:
                # 执行点击
                click_node_name = "Noctoyager_Click"
                click_config = {
                    "action": {
                        "type": "Click",
                        "param": {
                            "position": click_position
                        }
                    }
                }
                
                context.override_pipeline({click_node_name: click_config})
                action_result = context.run_action(click_node_name, argv.image)
                
                if action_result and action_result.success:
                    result["success"] = True
                    result["message"] = f"点击{click_target}成功"
                    result["found_target"] = True
                else:
                    result["message"] = "点击执行失败"
            
        else:
            result["message"] = f"未知的动作类型: {action_type}"
        
        return CustomAction.Result(json.dumps(result))
        
    except Exception as e:
        logger.error(f"NoctoyagerAction 执行失败: {e}")
        error_result = {
            "success": False,
            "message": f"执行失败: {str(e)}",
            "swipe_count": 0,
            "found_target": False
        }
        return CustomAction.Result(json.dumps(error_result))