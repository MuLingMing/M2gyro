from typing import Optional, Dict, Type
from .base import PlatformBase
from maa.controller import Controller


class PlatformFactory:
    """平台工厂类"""
    
    # 平台类型映射
    _platform_classes: Dict[str, Type[PlatformBase]] = {}
    
    @classmethod
    def register_platform(cls, platform_type: str, platform_class: Type[PlatformBase]):
        """注册平台类
        
        Args:
            platform_type: 平台类型
            platform_class: 平台类
        """
        cls._platform_classes[platform_type] = platform_class
    
    @classmethod
    def create_platform(cls, platform_type: str, controller: Controller) -> Optional[PlatformBase]:
        """创建平台实例
        
        Args:
            platform_type: 平台类型
            controller: 控制器实例
            
        Returns:
            平台实例
        """
        # 动态导入平台类
        if platform_type == "win32":
            from .win32 import Win32Platform
            cls.register_platform("win32", Win32Platform)
        elif platform_type == "adb":
            from .adb import AdbPlatform
            cls.register_platform("adb", AdbPlatform)
        
        # 创建平台实例
        platform_class = cls._platform_classes.get(platform_type)
        if platform_class:
            return platform_class(controller)
        return None
    
    @classmethod
    def detect_platform(cls, controller: Controller) -> str:
        """检测控制器类型

        Args:
            controller: 控制器实例

        Returns:
            str: 平台类型
        """
        if controller is None:
            return 'adb'

        if hasattr(controller, 'uuid'):
            uuid = str(getattr(controller, 'uuid', '')).lower()
            if 'adb' in uuid or 'android' in uuid or 'emulator' in uuid:
                return 'adb'
            if 'win32' in uuid or 'windows' in uuid:
                return 'win32'

        if hasattr(controller, 'info'):
            info = str(getattr(controller, 'info', '')).lower()
            if 'adb' in info or 'android' in info:
                return 'adb'
            if 'win32' in info or 'windows' in info:
                return 'win32'

        return 'adb'
