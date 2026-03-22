
from maa.context import Context
from maa.custom_action import CustomAction
from utils import logger


class CheckResolution(CustomAction):
    """
    检查当前模拟器分辨率是否符合预期（16:9）。
    """

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:

        width, height = context.tasker.controller.resolution
        aspect_ratio = width / height
        target_ratio = 16 / 9

        # 允许 1% 的误差
        if abs(aspect_ratio - target_ratio) / target_ratio > 0.01:
            logger.error(f"当前模拟器/游戏分辨率不是16:9! 当前: {width}x{height}")
        elif height < 720:
            logger.warning(f"当前模拟器/游戏分辨率高度低于720! 当前: {width}x{height}")
        else:
            return CustomAction.RunResult(success=True)
        logger.info("建议调整至16:9（如1280x720）")
        return CustomAction.RunResult(success=True)