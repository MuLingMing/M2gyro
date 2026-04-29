# -*- coding: utf-8 -*-
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
from maa.context import RecognitionDetail
from maa.custom_recognition import CustomRecognition
from utils.logger import logger
import json
import time
from param_merger import ParamMerger

# 常量定义
DEFAULT_INTERVAL = 2.0
DEFAULT_TOTAL_TIME = 90
MIN_SLEEP_TIME = 2.0


class Countdown(CustomRecognition):
    """
    倒计时执行识别器

    功能说明：
    1. 总体倒计时功能
       - 总倒计时时间：total_time秒（默认值90秒）
       - 间隔interval秒识别一次节点列表

    2. 节点分类与处理
        2.1 Interrupt: ["A1", {"name": "A2", "run": "True", "interval": 2, "hit": True, "delay": 1}]
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
        "entry": 入口节点名称，默认无入口节点,
        "Interrupt": ["A1", {"name": "A2", "run": "True", "interval": 2, "hit": True, "delay": 1, "start_after": 10, "max_recognitions": 3}],
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
        - start_after: 计时开始后多少秒再开始判定该节点，默认0秒（立即开始）
        - max_recognitions: 是否识别或最大识别成功次数，只有识别成功时才会递减，默认true无限制，false则不识别
    - logger: 是否开启日志，默认False

    备注：
    - total_time=0时，进入无限循环模式
    - 支持节点格式：{"name": "A1", "run": "True", "interval": 2, "hit": True, "start_after": 10, "max_recognitions": 3}
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
                        "run": (bool, int),  # run 可以是布尔值或整数
                        "interval": (int, float),  # interval 可以是整数或浮点数
                        "hit": bool,
                        "delay": (int, float),  # delay 可以是整数或浮点数
                        "start_after": (int, float),  # start_after 可以是整数或浮点数
                        "max_recognitions": (bool, int),  # max_recognitions 可以是布尔值或整数
                    }
                    # 节点列表类型（字符串、对象或数组）
                    node_list_type = (str, node_schema, list)
                    # 完整 schema
                    schema = {
                        "total_time": int,  # 总倒计时时间（秒）
                        "entry": node_list_type,
                        "Interrupt": node_list_type,  # 可以是字符串、对象或数组
                        "Continue": node_list_type,  # 可以是字符串、对象或数组
                        "Over": node_list_type,  # 可以是字符串、对象或数组
                        "logger": bool,
                    }
                    params = ParamMerger.merge(
                        "reco", custom_recognition_param, attach_params, schema
                    )
        except json.JSONDecodeError as e:
            logger.error(f"Countdown: 参数解析失败: {e}")
            return CustomRecognition.AnalyzeResult(box=None, detail={"hit": False})

        # 必要参数
        total_time = params.get("total_time", DEFAULT_TOTAL_TIME)  # 总倒计时时间（秒）
        entry = params.get("entry", [])  # 入口节点名称，默认无入口节点
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
        if not isinstance(entry, list):
            entry = [entry]

        # 检查入口节点是否存在
        if entry:
            # 入口节点识别成功则进入倒计时循环，未识别到则返回失败结果
            parsed_entry = [self._parse_node(node) for node in entry]
            for parsed in parsed_entry:
                result = self._run_recognition(context, parsed)
                if result:
                    if logger_enable:
                        logger.debug(
                            f"Countdown: {argv.node_name} 识别到入口节点 {parsed.get('name')}"
                        )
                    break
            else:
                # 未识别到入口节点，返回失败结果
                if logger_enable:
                    logger.debug(
                        f"Countdown: {argv.node_name} 未识别到入口节点 {[item.get('name') for item in parsed_entry]}"
                    )
                return CustomRecognition.AnalyzeResult(box=None, detail={"hit": False})

        # 倒计时开始
        if logger_enable:
            logger.debug(f"Countdown: {argv.node_name} 开始倒计时 {total_time} 秒")

        start_time = time.monotonic()

        # 预处理节点参数，创建追踪器
        interrupt_trackers = [self._NodeTracker(self._parse_node(node), start_time) for node in Interrupt]
        continue_trackers = [self._NodeTracker(self._parse_node(node), start_time) for node in Continue]
        parsed_over = [self._parse_node(node) for node in Over]

        # 主循环
        while True:
            current_time = time.monotonic()
            elapsed = current_time - start_time
            
            # 检查倒计时结束
            if total_time > 0 and elapsed > total_time:
                break
            
            # 检查停止标志
            if context.tasker.stopping:
                if logger_enable:
                    logger.debug(f"Countdown: {argv.node_name} 任务被停止")
                return CustomRecognition.AnalyzeResult(box=None, detail={"hit": False})
            
            # 一次性获取截图，避免重复获取
            image = context.tasker.controller.post_screencap().wait().get()
            
            # 检查 Interrupt 节点
            for tracker in interrupt_trackers:
                if not tracker.should_check(current_time, elapsed):
                    continue
                
                tracker.on_check(current_time)
                result = self._run_recognition(context, tracker.parsed, image)
                if result and result.hit:
                    tracker.on_hit()
                    if logger_enable:
                        logger.debug(f"Countdown: {argv.node_name} 识别到中断节点 {tracker.parsed.get('name')}")
                    return CustomRecognition.AnalyzeResult(
                        box=result.box,
                        detail={"hit": tracker.hit}
                    )
            
            # 检查 Continue 节点
            for tracker in continue_trackers:
                if not tracker.should_check(current_time, elapsed):
                    continue
                
                if logger_enable:
                    logger.debug(f"Countdown: {argv.node_name} 检查继续节点 {tracker.parsed.get('name')}")
                tracker.on_check(current_time)
                result = self._run_recognition(context, tracker.parsed, image)
                if result and result.hit:
                    tracker.on_hit()
                    if logger_enable:
                        logger.debug(f"Countdown: {argv.node_name} 识别到继续节点 {tracker.parsed.get('name')}")
            
            # 计算下次检查时间
            next_checks = []
            # 检查 Interrupt 节点的下次检查时间
            for tracker in interrupt_trackers:
                if tracker.is_disabled or (tracker.remaining is not None and tracker.remaining <= 0):
                    continue
                next_checks.append(max(tracker.get_next_check_time(), tracker.available_time))
            # 检查 Continue 节点的下次检查时间
            for tracker in continue_trackers:
                if tracker.is_disabled or (tracker.remaining is not None and tracker.remaining <= 0):
                    continue
                next_checks.append(max(tracker.get_next_check_time(), tracker.available_time))
            
            # 计算睡眠时间
            sleep_time = MIN_SLEEP_TIME
            if next_checks:
                check_time = time.monotonic()
                sleep_duration = max(next_checks) - check_time
                if sleep_duration > 0:
                    sleep_time = min(MIN_SLEEP_TIME, sleep_duration)
            time.sleep(sleep_time)
            
            # 日志输出
            if logger_enable and total_time > 0:
                log_time = time.monotonic()
                remaining = total_time - (log_time - start_time)
                logger.info(f"Countdown: {argv.node_name} 倒计时 {remaining} 秒")
        
        # 任务超时，执行 Over 节点
        if parsed_over:
            image = context.tasker.controller.post_screencap().wait().get()
            for parsed in parsed_over:
                hit = parsed.get("hit", True)
                result = self._run_recognition(context, parsed, image)
                if result and result.hit:
                    logger.debug(
                        f"Countdown: {argv.node_name} 任务超时！执行超时节点 {parsed.get('name')}"
                    )
                    return CustomRecognition.AnalyzeResult(
                        box=result.box, detail={"hit": hit}
                    )

        return CustomRecognition.AnalyzeResult(box=None, detail={"hit": False})


    class _NodeTracker:
        """节点追踪器，用于管理单个节点的状态"""
        def __init__(self, parsed: dict, start_time: float):
            self.parsed = parsed
            self.interval = parsed.get("interval", DEFAULT_INTERVAL)
            self.start_after = parsed.get("start_after", 0.0)
            self.hit = parsed.get("hit", True)
            self.timestamp = start_time
            max_rec = parsed.get("max_recognitions", True)
            self.remaining = max_rec if isinstance(max_rec, int) and max_rec >= 0 else None
            self.is_disabled = max_rec is False
            self.available_time = start_time + self.start_after
        
        def should_check(self, current_time: float, elapsed: float) -> bool:
            """检查是否应该进行识别"""
            if self.is_disabled:
                return False
            if elapsed < self.start_after:
                return False
            if self.remaining is not None and self.remaining <= 0:
                return False
            if current_time - self.timestamp < self.interval:
                return False
            return True
        
        def get_next_check_time(self) -> float:
            """获取下次检查时间"""
            return self.timestamp + self.interval
        
        def on_check(self, current_time: float):
            """更新检查时间戳"""
            self.timestamp = current_time
        
        def on_hit(self):
            """识别成功时调用"""
            if self.remaining is not None:
                self.remaining -= 1



    def _run_recognition(
        self, context: Context, parsed: dict | None, image=None
    ) -> RecognitionDetail | None:
        """
        执行识别判定
        参数:
        - context: 上下文对象，用于执行节点识别和任务
        - parsed: 节点参数字典，包含name, run, delay
        - image: 可选的已有截图
        返回值:
        - RecognitionDetail|None: 识别结果
        """
        if not parsed:
            return None
        name = parsed.get("name", "")
        if not name:
            return None
        
        run = parsed.get("run", True)
        delay = parsed.get("delay", 0.0)
        
        try:
            # 执行节点的识别任务
            if image is None:
                image = context.tasker.controller.post_screencap().wait().get()
            result = context.run_recognition(name, image=image)
            
            if result and result.hit:
                if delay > 0:
                    # 增加二次识别，确保识别结果稳定
                    time.sleep(delay)
                    image = context.tasker.controller.post_screencap().wait().get()
                    result = context.run_recognition(name, image=image)
                    if not result or not result.hit:
                        return None
                
                # 执行节点任务
                if isinstance(run, bool) and run:
                    self._run_node(context, name)
                elif isinstance(run, int) and run > 0:
                    parsed["run"] = run - 1
                    self._run_node(context, name)
                return result
        except Exception as e:
            logger.error(f"Countdown: 执行节点 {name} 失败: {e}")
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

    def _parse_number(self, value, default, min_val=None):
        """
        解析数字参数
        参数:
        - value: 要解析的值
        - default: 默认值
        - min_val: 最小值，可选
        返回值: 解析后的数字
        """
        if isinstance(value, (int, float)):
            result = value
        else:
            try:
                result = float(value)
            except:
                result = default
        if min_val is not None and result < min_val:
            result = default
        return result

    def _parse_bool_or_int(self, value, default=True):
        """
        解析布尔或整数参数（用于 max_recognitions）
        参数:
        - value: 要解析的值
        - default: 默认值
        返回值: bool 或 int
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value if value >= 0 else default
        
        if isinstance(value, str):
            if value.lower() == "true":
                return True
            if value.lower() == "false":
                return False
            try:
                result = int(value)
                return result if result >= 0 else default
            except:
                pass
        return default

    def _parse_node(self, param: str | dict) -> dict:
        """
        解析节点参数
        param格式为{"name": "A1", "run": "True", "interval": 2, "hit": True, "delay": 1, "start_after": 10, "max_recognitions": 3}
        默认run为True，对齐_run_recognition逻辑
        max_recognitions表示最大识别成功次数
        """
        if not param:
            return {"name": ""}
        if isinstance(param, str):
            return {"name": param}
        if isinstance(param, dict):
            name = param.get("name", "")
            run = param.get("run", True)
            
            # 处理字符串形式的 run 参数
            if isinstance(run, str):
                run = run.lower() == "true"
            
            # 解析各个参数
            interval = self._parse_number(param.get("interval", DEFAULT_INTERVAL), DEFAULT_INTERVAL, 0)
            delay = self._parse_number(param.get("delay", 0.0), 0.0, 0)
            start_after = self._parse_number(param.get("start_after", 0.0), 0.0, 0)
            max_recognitions = self._parse_bool_or_int(param.get("max_recognitions", True))
            hit = param.get("hit", True)
            
            return {
                "name": name,
                "run": run,
                "interval": interval,
                "hit": hit,
                "delay": delay,
                "start_after": start_after,
                "max_recognitions": max_recognitions,
            }
        return {}
