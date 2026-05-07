# -*- coding: utf-8 -*-
"""
倒计时执行action，具有以下功能：
1. 总体倒计时total_time秒（默认值90秒）
2. 识别节点列表，分类为Interrupt,Continue,Over
    2.1 Interrupt:
    - 间隔时间interval秒
    - 识别到A1，执行对应节点并结束
    - 识别到A2，执行对应节点并结束
    2.2 Continue:
    - 间隔时间interval秒
    - 识别到B1，执行对应节点并继续
    - 识别到B2，执行对应节点并继续
    2.3 Over:
    - 倒计时超时，执行对应节点并结束
"""

import json
import time
from dataclasses import dataclass
from itertools import chain

from maa.context import Context, RecognitionDetail
from maa.custom_action import CustomAction
from utils.logger import logger
from param_merger import ParamMerger

DEFAULT_INTERVAL = 2.0
DEFAULT_TOTAL_TIME = 90
MIN_SLEEP_TIME = 2.0


class Countdown(CustomAction):
    """
    倒计时执行动作器

    注册方式：通过 agent/custom.json 动态注册，不引入装饰器

    参数格式：
    {
        "total_time": 90,
        "Interrupt": ["A1", {"name": "A2", "run": "True", "interval": 2, "delay": 1, "start_after": 10, "max_reco": 3}],
        "Continue": "B",
        "Over": ["C"]
    }

    字段说明：
    - total_time: 总倒计时时间（秒），默认90秒，0为无限循环
    - Interrupt: 中断节点列表，识别到该节点时，执行对应节点并结束
    - Continue: 继续节点列表，识别到该节点时，执行对应节点并继续识别
    - Over: 超时节点列表，超时时执行对应节点并结束。仅使用 name、run、delay 参数

    节点格式：
    - 简单格式："A1"
    - 对象格式：{"name": "A1", "run": "True", "interval": 2, "delay": 1, "start_after": 10, "max_reco": 3}
    - run: 是否执行节点任务，可以是布尔值或整数（限制执行次数）
    - interval: 识别间隔时间（秒），默认2秒
    - delay: 二次识别延迟（秒），用于确保识别稳定
    - start_after: 计时开始后多少秒再开始判定该节点，默认0秒
    - max_reco: 最大尝试识别次数，默认true无限制，false则不识别

    run 与 max_reco 交互（正交关系，max_reco 优先级更高）：
    - max_reco 控制「是否参与识别」：每次尝试识别时递减，耗尽后节点不再参与识别
    - run 控制「识别成功后是否执行任务」：识别成功且执行任务时递减
    - max_reco 耗尽 → 节点完全失效（不再识别）；run 耗尽 → 节点仍参与识别但不执行任务
    - run=false, max_reco=true → 仅识别不执行任务
    - run=true, max_reco=false → 跳过识别也不运行
    """

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        """
        执行倒计时逻辑

        参数:
        - context: 上下文对象，用于执行节点识别和任务
        - argv: 运行参数，包含节点名称和自定义参数

        返回值:
        - CustomAction.RunResult: 执行结果
        - 成功: success=True
        - 失败: success=False

        执行流程:
        1. 解析并验证参数
        2. 初始化时间戳
        3. 循环检查Interrupt和Continue节点
        4. 动态计算sleep时间
        5. 超时执行Over节点
        """
        params = self._parse_params(argv, context)
        if params is None:
            return CustomAction.RunResult(success=False)

        total_time = params.get("total_time", DEFAULT_TOTAL_TIME)
        Interrupt = params.get("Interrupt", [])
        Continue = params.get("Continue", [])
        Over = params.get("Over", [])

        if not Interrupt and not Continue and not Over:
            logger.error(f"Countdown: {argv.node_name} 未配置任何节点，无法执行倒计时")
            return CustomAction.RunResult(success=False)
        if not isinstance(Interrupt, list):
            Interrupt = [Interrupt]
        if not isinstance(Continue, list):
            Continue = [Continue]
        if not isinstance(Over, list):
            Over = [Over]

        start_time = time.monotonic()

        interrupt_trackers = [
            _NodeTracker(self._parse_node(node), start_time) for node in Interrupt
        ]
        continue_trackers = [
            _NodeTracker(self._parse_node(node), start_time) for node in Continue
        ]
        parsed_over = [self._parse_node(node) for node in Over]

        while True:
            current_time = time.monotonic()
            elapsed = current_time - start_time

            if total_time > 0 and elapsed >= total_time:
                break

            if context.tasker.stopping:
                return CustomAction.RunResult(success=False)

            all_trackers = chain(interrupt_trackers, continue_trackers)
            need_check = any(
                t.should_check(current_time, elapsed) for t in all_trackers
            )
            if not need_check:
                sleep_time = self._calculate_sleep(
                    chain(interrupt_trackers, continue_trackers),
                    current_time,
                    total_time,
                    elapsed,
                )
                time.sleep(sleep_time)
                continue

            image = context.tasker.controller.post_screencap().wait().get()

            for tracker in interrupt_trackers:
                if not tracker.should_check(current_time, elapsed):
                    continue
                tracker.on_check(current_time)
                result = self._recog_and_confirm(context, tracker, image)
                if result and result.hit:
                    return CustomAction.RunResult(success=True)

            for tracker in continue_trackers:
                if not tracker.should_check(current_time, elapsed):
                    continue
                tracker.on_check(current_time)
                self._recog_and_confirm(context, tracker, image)

            sleep_time = self._calculate_sleep(
                chain(interrupt_trackers, continue_trackers),
                current_time,
                total_time,
                elapsed,
            )
            time.sleep(sleep_time)

        if parsed_over:
            image = context.tasker.controller.post_screencap().wait().get()
            for config in parsed_over:
                if not config.name:
                    continue
                try:
                    result = context.run_recognition(config.name, image=image)
                    if not result or not result.hit:
                        continue
                    if config.delay > 0:
                        time.sleep(config.delay)
                        confirm_image = (
                            context.tasker.controller.post_screencap().wait().get()
                        )
                        result = context.run_recognition(
                            config.name, image=confirm_image
                        )
                        if not result or not result.hit:
                            continue
                    if config.run:
                        self._run_task(context, config.name)
                    return CustomAction.RunResult(success=True)
                except Exception as e:
                    logger.error(f"Countdown: 执行 Over 节点 {config.name} 失败: {e}")

        return CustomAction.RunResult(success=False)

    def _parse_params(self, argv: CustomAction.RunArg, context: Context) -> dict | None:
        """解析并合并参数，失败时返回 None"""
        try:
            custom_action_param: dict = json.loads(argv.custom_action_param)
            if node_data := context.get_node_data(argv.node_name):
                attach_params = node_data.get("attach", {})
            else:
                attach_params = {}
            if not custom_action_param:
                return {}
            if not attach_params:
                return custom_action_param
            node_schema = {
                "name": str,
                "run": (bool, int),
                "interval": (int, float),
                "delay": (int, float),
                "start_after": (int, float),
                "max_reco": (bool, int),
            }
            node_list_type = (str, node_schema, list)
            schema = {
                "total_time": int,
                "Interrupt": node_list_type,
                "Continue": node_list_type,
                "Over": node_list_type,
            }
            return ParamMerger.merge(
                "action", custom_action_param, attach_params, schema
            )
        except Exception as e:
            logger.error(f"Countdown: 参数解析失败: {e}")
            return None

    def _calculate_sleep(
        self, trackers, current_time: float, total_time: int, elapsed: float
    ) -> float:
        """
        计算下一次循环的 sleep 时间

        优先级：
        1. 最近一次检查时间点
        2. 最小 interval
        3. total_time 剩余时间
        4. MIN_SLEEP_TIME 兜底
        """
        active_intervals = []
        next_checks = []
        for tracker in trackers:
            if tracker.is_exhausted:
                continue
            active_intervals.append(tracker.interval)
            next_checks.append(
                max(tracker.get_next_check_time(), tracker.available_time)
            )

        min_interval = min(active_intervals) if active_intervals else MIN_SLEEP_TIME
        sleep_time = min_interval

        if next_checks:
            sleep_duration = min(next_checks) - current_time
            if sleep_duration > 0:
                sleep_time = min(sleep_time, sleep_duration)

        if total_time > 0:
            remaining = total_time - elapsed
            sleep_time = min(sleep_time, remaining)

        return max(sleep_time, 0)

    def _recog_and_confirm(
        self, context: Context, tracker: "_NodeTracker", image
    ) -> RecognitionDetail | None:
        """
        识别 + 二次确认 + 执行任务

        流程：
        1. 执行识别
        2. 命中后，如有 delay 则等待后二次确认
        3. 确认通过后，根据 run 配置决定是否执行节点任务
        """
        config = tracker.config
        if not config.name:
            return None
        try:
            result = context.run_recognition(config.name, image=image)
            if not result or not result.hit:
                return None

            if config.delay > 0:
                time.sleep(config.delay)
                confirm_image = context.tasker.controller.post_screencap().wait().get()
                result = context.run_recognition(config.name, image=confirm_image)
                if not result or not result.hit:
                    return None

            if isinstance(config.run, bool) and config.run:
                self._run_task(context, config.name)
            elif isinstance(config.run, int) and config.run > 0:
                self._run_task(context, config.name)
                if tracker.run_remaining is not None:
                    tracker.run_remaining -= 1

            return result
        except Exception as e:
            logger.error(f"Countdown: 执行节点 {config.name} 失败: {e}")
        return None

    def _run_task(self, context: Context, node_name: str) -> None:
        """执行节点任务"""
        try:
            context.run_task(node_name)
        except Exception as e:
            logger.error(f"Countdown: 执行节点 {node_name} 失败: {e}")

    def _parse_node(self, param: str | dict | None) -> "NodeConfig":
        """解析节点参数为 NodeConfig"""
        if not param:
            return NodeConfig()
        if isinstance(param, str):
            return NodeConfig(name=param)
        if isinstance(param, dict):
            run = param.get("run", True)
            if isinstance(run, str):
                run = run.lower() == "true"
            return NodeConfig(
                name=param.get("name", ""),
                run=run,
                interval=self._parse_number(
                    param.get("interval", DEFAULT_INTERVAL), DEFAULT_INTERVAL, 0
                ),
                delay=self._parse_number(param.get("delay", 0.0), 0.0, 0),
                start_after=self._parse_number(param.get("start_after", 0.0), 0.0, 0),
                max_reco=self._parse_bool_or_int(param.get("max_reco", True)),
            )
        return NodeConfig()

    @staticmethod
    def _parse_number(value, default: float, min_val: float | None = None) -> float:
        try:
            result = float(value)
        except (ValueError, TypeError):
            result = default
        if min_val is not None and result < min_val:
            result = default
        return result

    @staticmethod
    def _parse_bool_or_int(value, default: bool | int = True) -> bool | int:
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
            except (ValueError, TypeError):
                pass
        return default


@dataclass
class NodeConfig:
    """
    节点配置，由 _parse_node 解析生成

    字段说明:
    - name: 节点名称，用于 run_recognition / run_task
    - run: 是否执行节点任务，True=无条件执行，False=仅识别不执行，int=限制执行次数
    - interval: 识别间隔时间（秒）
    - delay: 二次识别延迟（秒），用于确保识别稳定
    - start_after: 计时开始后多少秒再开始判定该节点
    - max_reco: 最大尝试识别次数，True=无限制，False=跳过识别，int=限制次数
    """

    name: str = ""
    run: bool | int = True
    interval: float = DEFAULT_INTERVAL
    delay: float = 0.0
    start_after: float = 0.0
    max_reco: bool | int = True


class _NodeTracker:
    """
    节点追踪器，管理单个节点的识别状态

    状态维度（正交关系）：
    - remaining（max_reco）：控制「是否参与识别」，每次 on_check 递减
    - run_remaining（run）：控制「识别成功后是否执行任务」，在 _recog_and_confirm 中递减

    is_exhausted 仅检查 remaining（max_reco），即 max_reco 优先级更高：
    - remaining 耗尽 → 节点不再参与识别
    - run_remaining 耗尽 → 节点仍参与识别，但不执行任务

    max_reco 语义：
    - True  → remaining = None（无限制识别）
    - False → remaining = 0（跳过识别，节点直接失效）
    - int   → remaining = n（尝试识别 n 次后失效）

    run 语义：
    - True  → run_remaining = None（识别成功后无条件执行任务）
    - False → run_remaining = 0（仅识别不执行任务）
    - int   → run_remaining = n（识别成功后最多执行 n 次任务）
    """

    def __init__(self, config: NodeConfig, start_time: float):
        self.config = config
        self.timestamp = start_time
        self.available_time = start_time + config.start_after

        max_rec = config.max_reco
        if max_rec is False:
            self.remaining = 0
        elif isinstance(max_rec, int) and max_rec >= 0:
            self.remaining = max_rec
        else:
            self.remaining = None

        run = config.run
        if isinstance(run, bool):
            self.run_remaining = None
        elif isinstance(run, int) and run >= 0:
            self.run_remaining = run
        else:
            self.run_remaining = None

    @property
    def is_exhausted(self) -> bool:
        return self.remaining is not None and self.remaining <= 0

    def should_check(self, current_time: float, elapsed: float) -> bool:
        if self.is_exhausted:
            return False
        if elapsed < self.config.start_after:
            return False
        if current_time - self.timestamp < self.config.interval:
            return False
        return True

    def get_next_check_time(self) -> float:
        return self.timestamp + self.config.interval

    def on_check(self, current_time: float):
        self.timestamp = current_time
        if self.remaining is not None:
            self.remaining -= 1
