# -*- coding: utf-8 -*-

from platform import node
from maa.context import RecognitionDetail

"""
倒计时执行recognition，具有以下功能：
1. 总体倒计时total_time秒（默认值60秒）
2. 识别节点列表，分类为Interrupt,Continue,Over
    2.1 Interrupt:
    - 间隔时间interval秒
    - 识别到A1，返回识别成功，该识别结束
    - 识别到A2，返回识别成功，该识别结束
    2.2 Continue:
    - 间隔时间interval秒
    - 识别到B1，该识别继续
    - 识别到B2，该识别继续
    2.3 Over:
    - 识别超时，执行对应节点并结束识别
"""

from maa.context import Context
from maa.custom_recognition import CustomRecognition
from utils.logger import logger
import json
import time
from general import ParamMerger

# 常量定义
DEFAULT_INTERVAL = 2.0
DEFAULT_TOTAL_TIME = 60
MIN_SLEEP_TIME = 2.0


class Countdown(CustomRecognition):
    """
    倒计时执行识别器

    功能说明：
    1. 总体倒计时功能
       - 总倒计时时间：total_time秒（默认值60秒）
       - 间隔interval秒识别一次节点列表

    2. 节点分类与处理
        2.1 Interrupt: ["A1", {"name": "A2", "run": "True", "interval": 2, "hit": True"}]
            - 间隔interval秒执行一次
            - 识别到A1/A2时，执行对应节点并结束
        2.2 Continue: "B"
           - 间隔interval秒执行一次
           - 识别到B时，执行对应节点并继续识别
        2.3 Over: ["C"]
           - 超时时，执行对应节点并结束

    3. 结束条件
       - 识别到Interrupt时结束
       - 倒计时结束时，执行Over节点的识别并结束

    逻辑切换：
    - total_time > 0: 执行倒计时模式
    - total_time = 0: 切换为无限时间模式

    参数格式：

    {
        "total_time": 总倒计时时间（秒），默认60秒,
        "Interrupt": ["A1", {"name": "A2", "run": "True", "interval": 2, "hit": True},
        "Continue": "B",
        "Over": ["C"],
        "logger": 是否开启日志，默认false
    }

    字段说明：
    - total_time: 总倒计时时间（秒），默认60秒
    - Interrupt: 中断节点列表，识别到该节点时，执行对应节点并结束
    - Continue: 继续节点列表，识别到该节点时，执行对应节点并继续识别
    - Over: 超时节点列表，超时时执行对应节点并结束
        - 支持节点格式：{"name": "C", "run": "True", "interval": 2, "hit": True}
        - interval: 识别name的间隔时间（秒），默认2秒
        - hit: 识别detail返回值，默认True
    - logger: 是否开启日志，默认False

    备注：
    - total_time=0时，进入无限循环模式
    - 支持节点格式：{"name": "A1", "run": "True", "interval": 2, "hit": True}
    - 节点内部逻辑为OR关系，调用节点的基础识别器实现，故不设为AND关系与反转逻辑
    """

    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        """
        执行倒计时识别逻辑

        参数:
        - context: 上下文对象，用于执行节点识别和任务
        - argv: 分析参数，包含节点名称和自定义参数

        返回值:
        - CustomRecognition.AnalyzeResult: 识别结果
        - 识别成功: detail={"hit": True}
        - 识别失败: detail={"hit": False}

        执行流程:
        1. 解析并验证参数
        2. 初始化时间戳
        3. 循环检查Interrupt和Continue节点
        4. 动态计算sleep时间
        5. 超时执行Over节点
        """
        # 解析参数
        try:
            custom_recognition_param: dict = json.loads(argv.custom_recognition_param)
            if node_data := context.get_node_data(argv.node_name):
                attach_params = node_data.get("attach", {})
            else:
                attach_params = {}
            if not custom_recognition_param:
                params = {}
            else:
                if not attach_params:
                    params = custom_recognition_param
                else:
                    # 节点对象的 schema
                    node_schema = {
                        "name": str,
                        "run": bool,  # run 可以是布尔值
                        "interval": (int, float),  # interval 可以是整数或浮点数
                        "hit": bool,
                    }
                    # 节点列表类型（字符串、对象或数组）
                    node_list_type = (str, node_schema, list)
                    # 完整 schema
                    schema = {
                        "total_time": int,
                        "Interrupt": node_list_type,  # 可以是字符串、对象或数组
                        "Continue": node_list_type,   # 可以是字符串、对象或数组
                        "Over": node_list_type,       # 可以是字符串、对象或数组
                        "logger": bool,
                    }
                    merger = ParamMerger(identifier_fields=["name"], schema=schema)
                    params = merger.merge_params("reco", custom_recognition_param, attach_params)
        except json.JSONDecodeError as e:
            logger.error(f"Countdown: 参数解析失败: {e}")
            return CustomRecognition.AnalyzeResult(box=None, detail={"hit": False})

        # 必要参数
        total_time = params.get("total_time", DEFAULT_TOTAL_TIME)  # 总倒计时时间（秒）
        Interrupt = params.get("Interrupt", [])  # ["A1","A2"]
        Continue = params.get("Continue", [])  # ["B"]
        Over = params.get("Over", [])  # ["C"]
        logger_enable = params.get("logger", False)  # 是否开启日志，默认False

        if not Interrupt and not Continue and not Over:
            logger.error(f"Countdown: {argv.node_name} 未配置任何节点，无法执行倒计时")
            return CustomRecognition.AnalyzeResult(box=None, detail={"hit": False})
        if not isinstance(Interrupt, list):
            Interrupt = [Interrupt]
        if not isinstance(Continue, list):
            Continue = [Continue]
        if not isinstance(Over, list):
            Over = [Over]

        # 倒计时开始
        if logger_enable:
            logger.info(f"Countdown: {argv.node_name} 开始倒计时 {total_time} 秒")

        start_time = time.monotonic()

        # 预处理节点参数
        parsed_interrupts = [self._parse_node(node) for node in Interrupt]
        parsed_continues = [self._parse_node(node) for node in Continue]

        # 使用字典管理时间戳，避免索引问题
        interrupt_timestamps = {i: start_time for i in range(len(parsed_interrupts))}
        continue_timestamps = {i: start_time for i in range(len(parsed_continues))}

        while time.monotonic() - start_time <= total_time or total_time <= 0:
            if context.tasker.stopping:
                return CustomRecognition.AnalyzeResult(box=None, detail={"hit": False})
            # 间隔interval秒运行一次节点识别
            for i, parsed in enumerate(parsed_interrupts):
                name = parsed.get("name", "")
                run = parsed.get("run", True)
                interval = parsed.get("interval", DEFAULT_INTERVAL)
                hit = parsed.get("hit", True)
                if time.monotonic() - interrupt_timestamps[i] >= interval:
                    interrupt_timestamps[i] = time.monotonic()
                    # 节点检查，识别到Interrupt，返回识别结果并终止循环
                    if result := self._run_recognition(context, name, run):
                        return CustomRecognition.AnalyzeResult(
                            box=result.box, detail={"hit": hit}
                        )
            # 检查是否需要执行Continue节点
            for i, parsed in enumerate(parsed_continues):
                name = parsed.get("name", "")
                run = parsed.get("run", True)
                interval = parsed.get("interval", DEFAULT_INTERVAL)
                hit = parsed.get("hit", True)
                if time.monotonic() - continue_timestamps[i] >= interval:
                    continue_timestamps[i] = time.monotonic()
                    self._run_recognition(context, name, run)

            # 计算下次检查时间
            next_checks = []
            for i, parsed in enumerate(parsed_interrupts):
                interval = parsed.get("interval", DEFAULT_INTERVAL)
                next_checks.append(interrupt_timestamps[i] + interval)
            for i, parsed in enumerate(parsed_continues):
                interval = parsed.get("interval", DEFAULT_INTERVAL)
                next_checks.append(continue_timestamps[i] + interval)

            if next_checks:
                # 计算下次检查时间，确保轮询间隔为 2 秒
                sleep_duration = max(next_checks) - time.monotonic()
                # 确保 sleep_time 为非负数
                sleep_time = max(MIN_SLEEP_TIME, sleep_duration)
                if sleep_time < 0:
                    sleep_time = MIN_SLEEP_TIME
                # 等待下次检查时间
                time.sleep(sleep_time)
            else:
                # 没有检查时间，等待 2 秒
                time.sleep(MIN_SLEEP_TIME)

            if logger_enable:
                logger.info(
                    f"Countdown: {argv.node_name} 倒计时 {total_time - (time.monotonic() - start_time)} 秒"
                )

        # 任务超时
        # 倒计时结束，执行Over节点
        if Over:
            for node in Over:
                node, run, _, hit = self._parse_node(node)
                if result := self._run_recognition(context, node, run):
                    if logger_enable:
                        logger.info(f"Countdown: {argv.node_name} 任务超时！")
                    return CustomRecognition.AnalyzeResult(
                        box=result.box, detail={"hit": hit}
                    )

        return CustomRecognition.AnalyzeResult(box=None, detail={"hit": False})

    def _run_recognition(
        self, context: Context, node_name: str, run: bool = True
    ) -> RecognitionDetail | None:
        """
        执行识别判定
        参数:
        - context: 上下文对象，用于执行节点识别和任务
        - node_name: 节点名称，为"A1"
        - run: 是否执行节点，默认True
        返回值:
        - RecognitionDetail|None: 识别结果，包含box字段
        """
        if not node_name:
            return None
        try:
            # 执行节点的识别任务
            # 获取截图
            result = context.run_recognition(
                node_name, image=context.tasker.controller.post_screencap().wait().get()
            )
            if result and result.hit:
                if run:
                    self._run_node(context, node_name)
                return result
        except Exception as e:
            logger.error(f"Countdown: 执行节点 {node_name} 失败: {e}")
        return None

    def _run_node(self, context: Context, node_name: str):
        """
        执行节点
        参数:
        - context: 上下文对象，用于执行节点任务
        - node_name: 节点名称，为"A1"
        """
        if not node_name:
            return None
        try:
            context.run_task(node_name)
        except Exception as e:
            logger.error(f"Countdown: 执行节点 {node_name} 失败: {e}")

    def _parse_node(self, param: str | dict) -> dict:
        """
        解析节点参数
        param格式为{"name": "A1", "run": "True", "interval": 2, "hit": True}
        默认run为True，对齐_run_recognition逻辑
        """
        if not param:
            return {}
        if isinstance(param, str):
            return {"name": param}
        if isinstance(param, dict):
            name = param.get("name", "")
            run = param.get("run", True)
            interval = param.get("interval", DEFAULT_INTERVAL)
            hit = param.get("hit", True)
            # 处理字符串形式的 run 参数
            if isinstance(run, str):
                run = run.lower() == "true"
            # 确保 interval 是数字
            if not isinstance(interval, (int, float)):
                try:
                    interval = float(interval)
                except:
                    interval = DEFAULT_INTERVAL
                if interval < 0:
                    interval = DEFAULT_INTERVAL
            parsed = {"name": name, "run": run, "interval": interval, "hit": hit}
            return parsed
        return {}
