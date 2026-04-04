# -*- coding: utf-8 -*-
"""
倒计时执行recognition，具有以下功能：
1. 总体倒计时total_time秒（默认值60秒）
2. 识别节点列表，分类为True[A1,A2],False[B1,B2],Continue[C1,C2]
    2.1 True_node:
    间隔时间2秒
    - 识别到A1，返回识别成功，该识别结束
    - 识别到A2，返回识别成功，该识别结束
    2.2 False_node:
    间隔时间2秒
    - 识别到B1，返回识别失败，该识别结束
    - 识别到B2，返回识别失败，该识别结束
    2.3 Continue_node:
    间隔时间interval秒
    - 识别到C1，执行C1，返回识别成功，该识别继续
    - 识别到C2，执行C2，返回识别成功，该识别继续
3. 倒计时结束，返回识别失败，该识别结束
"""

from maa.context import Context
from maa.custom_recognition import CustomRecognition
from utils.logger import logger
import json
import time


class Countdown(CustomRecognition):
    """
    倒计时执行recognition，具有以下功能：
    1. 总体倒计时total_time秒（默认值60秒）
    2. 间隔2秒识别一次节点列表，分类为True[A1,A2],False[B1,B2],Continue[C1,C2]
        2.1 True_node:
        间隔时间2秒
        - 识别到A1，返回识别成功，该识别结束
        - 识别到A2，返回识别成功，该识别结束
        2.2 False_node:
        间隔时间2秒
        - 识别到B1，返回识别失败，该识别结束
        - 识别到B2，返回识别失败，该识别结束
        2.3 Continue_node:
        间隔时间interval秒
        - 识别到C1，执行C1，返回识别成功，该识别继续
        - 识别到C2，执行C2，返回识别成功，该识别继续
    3. 倒计时结束，返回识别失败，该识别结束

    4. 逻辑切换：
    - 倒计时时间大于0，执行倒计时
    - 倒计时时间等于0，切换为无限时间
    - 倒计时时间小于0，切换为if_else逻辑
        - 使用continue_node进行判断
        - 如果识别到C1或C2，执行true_node中的节点
        - 如果未识别到C1或C2，执行false_node中的节点
    参数格式：
    {
        "total_time": 总倒计时时间（秒）,
        "interval": 执行Continue_node的间隔时间（秒）,
        "True_node": ["A1","A2"],
        "False_node": ["B1","B2"],
        "Continue_node": ["C1","C2"],
        "logger": 是否开启日志，默认False
        //备注：
        //total_time设为0时，倒计时时间无限循环
        //total_time设为小于0时，转换为if_else逻辑
    }

    字段说明：
    - total_time: 总倒计时时间（秒）
    - interval: 执行Continue_node的间隔时间（秒），默认5秒
    - True_node: 节点列表
    - False_node: 节点列表
    - Continue_node: 节点列表
    - logger: 是否开启日志，默认False
    """

    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        # 解析参数
        argv_dict: dict = json.loads(argv.custom_recognition_param)

        # 必要参数
        total_time = argv_dict.get("total_time", 60)  # 总倒计时时间（秒）
        interval = argv_dict.get("interval", 5)  # 执行Continue_node的间隔时间（秒）
        True_node = argv_dict.get("True_node", [])  # ["A1","A2"]
        False_node = argv_dict.get("False_node", [])  # ["B"]
        Continue_node = argv_dict.get("Continue_node", [])  # ["C"]
        logger_enable = argv_dict.get("logger", False)  # 是否开启日志，默认False

        if total_time >= 0:
            # 倒计时开始
            if logger_enable:
                logger.info(
                    f"CountdownAction: {argv.node_name} 开始倒计时 {total_time} 秒"
                )

            start_time = time.time()
            last_check_time = start_time
            last_continue_time = start_time

            while time.time() - start_time <= total_time or total_time == 0:
                # 间隔2秒运行一次
                if time.time() - last_check_time >= 2:
                    last_check_time = time.time()
                    # 节点检查，识别到True_node或False_node，返回识别结果并终止循环
                    if self._run_recognition(context, True_node):
                        return CustomRecognition.AnalyzeResult(
                            box=None, detail={"hit": True}
                        )
                    elif self._run_recognition(context, False_node):
                        return CustomRecognition.AnalyzeResult(
                            box=None, detail={"hit": False}
                        )
                # 检查是否需要执行Continue_node
                if time.time() - last_continue_time >= interval:
                    last_continue_time = time.time()
                    self._run_recognition(context, Continue_node, flag=True)

                time.sleep(0.5)

            # 倒计时结束，未识别到任何节点
            if logger_enable:
                logger.info(f"CountdownAction: {argv.node_name} 任务超时！")
            return CustomRecognition.AnalyzeResult(box=None, detail={"hit": False})

        else:
            # 倒计时时间小于0，切换为if_else逻辑
            if self._run_recognition(context, Continue_node):
                self._run_nodes(context, True_node)
            elif self._run_recognition(context, False_node):
                self._run_nodes(context, False_node)
            return CustomRecognition.AnalyzeResult(box=None, detail={"hit": True})

    def _run_recognition(
        self, context: Context, nodes: str | list, flag: bool = False
    ) -> bool:
        """
        执行识别判定
        """
        if not nodes:
            return False
        if isinstance(nodes, str):
            nodes = [nodes]
        for node in nodes:
            try:
                # 执行节点的识别
                result = context.run_recognition(
                    node, image=context.tasker.controller.cached_image
                )
                if result and result.hit:
                    if flag:
                        self._run_nodes(context, node)
                    return True
            except Exception as e:
                logger.error(f"CountdownAction: 执行节点 {node} 失败: {e}")
        return False

    def _run_nodes(self, context: Context, nodes: str | list):
        """
        执行节点列表
        """
        if not nodes:
            return
        if isinstance(nodes, str):
            nodes = [nodes]
        for node in nodes:
            try:
                context.run_task(node)
            except Exception as e:
                logger.error(f"CountdownAction: 执行节点 {node} 失败: {e}")
