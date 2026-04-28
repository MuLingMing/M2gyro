# OperationRecording 框架使用指南

版本: 1.2.0

## 框架特性

- 自动动作注册：通过装饰器自动注册动作，无需手动修改代码
- 统一 JSON 参数模板：支持灵活的参数定义和验证
- 控制器自动检测：自动识别 ADB/Win32 平台
- 平台扩展支持：轻松添加新的平台实现
- 零配置扩展：添加新动作只需创建文件，无需修改其他文件
- 时间线模式：支持复杂动作序列、并行动作叠加、动作优先级
- 类人化效果：随机反应时间，平滑移动路径、动作间隔延迟
- 双模式执行：自动检测普通模式和时间线模式
- 安全停止：支持接收停止通知，释放全部按键

## 快速开始

### 1. 添加新动作

步骤 1：在 `actions/basic/` 或 `actions/advanced/` 目录创建动作文件

```python
# actions/basic/new_action.py
from ..base import ActionBase
from .. import register_action


@register_action("new_action")
class NewAction(ActionBase):
    """新动作"""

    @property
    def name(self) -> str:
        return "new_action"

    def execute(self, params: dict) -> bool:
        """执行动作

        Args:
            params: 动作参数

        Returns:
            bool: 执行是否成功
        """
        return self._platform.new_action(**params)
```

步骤 2：在 `config/default.json` 中添加动作配置

```json
{
  "new_action": {
    "description": "新动作",
    "parameters": {
      "param1": {
        "type": "string",
        "required": true
      },
      "param2": {
        "type": "number",
        "required": false,
        "default": 1.0
      }
    }
  }
}
```

步骤 3：在平台类中实现动作方法

```python
# platforms/win32/win32_platform.py
def new_action(self, param1, param2=1.0):
    """执行新动作"""
    # 实现 Win32 平台的新动作
    return True

# platforms/adb/adb_platform.py
def new_action(self, param1, param2=1.0):
    """执行新动作"""
    # 实现 ADB 平台的新动作
    return True
```

### 2. 使用动作

普通模式（顺序执行）：

```json
[
  {
    "action": "move",
    "params": {
      "direction": "forward",
      "duration": 1.0
    }
  },
  {
    "action": "jump",
    "params": {}
  },
  {
    "action": "charge_attack",
    "params": {
      "duration": 2.0
    }
  },
  {
    "action": "crouch",
    "params": {}
  }
]
```

时间线模式（复杂序列）：

```json
{
  "operations": [
    {"action": "move", "params": {"direction": "left"}, "duration": 2.0},
    {"action": "wait", "duration": 2.0},
    {
      "action": "move",
      "params": {"direction": "forward"},
      "duration": 8.0,
      "overlays": [{"action": "dodge", "params": {"direction": "forward"}, "at": 3.0}]
    },
    {
      "action": "move",
      "params": {"direction": "left"},
      "duration": 12.0,
      "overlays": [{"action": "jump", "at": 5.0}]
    }
  ],
  "loop_count": 1
}
```

## 框架架构

### 目录结构

```text
OperationRecording/
├── __init__.py              # 模块入口，版本 1.2.0
├── README.md
├── test_advanced_system.py   # 高级系统测试
├── test_integration.py       # 集成测试
├── test_integration_simple.py # 简单集成测试
├── action_types/            # 数据类型
│   ├── __init__.py
│   ├── operation.py         # Operation 数据结构
│   └── operation_param.py   # OperationParam 数据结构
├── actions/                  # 动作系统
│   ├── __init__.py
│   ├── base.py              # ActionBase 抽象基类
│   ├── registry.py          # ActionRegistry 注册表
│   ├── auto_register.py     # @register_action 装饰器
│   ├── operation_record_action.py  # MaaFramework 入口
│   ├── basic/              # 基本动作（8个）
│   │   ├── move_action.py
│   │   ├── jump_action.py
│   │   ├── dodge_action.py
│   │   ├── turn_action.py
│   │   ├── interact_action.py
│   │   ├── charge_attack_action.py  # 蓄力攻击
│   │   └── crouch_action.py        # 下蹲
│   └── advanced/            # 高级动作
│       └── spiral_leap_action.py
├── config/                  # 配置系统
│   ├── __init__.py
│   ├── manager.py           # ConfigManager
│   └── default.json         # 默认配置
├── core/                    # 核心功能
│   ├── __init__.py
│   ├── humanizer.py         # Humanizer 类人化处理器
│   ├── operation_executor.py # OperationExecutor 执行器
│   ├── operation_parser.py  # OperationParser 解析器
│   └── timeline_manager.py  # ActionTimeline 时间线管理
└── platforms/               # 平台实现
    ├── __init__.py
    ├── base.py              # PlatformBase 抽象基类
    ├── factory.py           # PlatformFactory 工厂
    ├── win32/              # Win32 平台
    │   ├── __init__.py
    │   └── win32_platform.py
    └── adb/                # ADB 平台
        ├── __init__.py
        └── adb_platform.py
```

### 核心组件

| 组件 | 说明 |
| :--- | :--- |
| ActionBase | 动作基类，所有动作都继承自它 |
| ActionRegistry | 动作注册表，管理所有动作 |
| PlatformBase | 平台基类，定义平台接口（含 `release_all()` 方法） |
| PlatformFactory | 平台工厂，创建平台实例 |
| OperationExecutor | 操作执行器，支持双模式执行，含停止响应 |
| OperationParser | 参数解析器，自动检测模式 |
| ActionTimeline | 时间线管理器，支持复杂序列 |
| Humanizer | 类人化处理器，添加随机效果 |

### 平台检测

平台类型通过 MaaFramework 的 `Controller` 属性自动检测：

- **ADB 平台**：检测 `uuid` 或 `info` 中包含 `adb`、`android`、`emulator` 字符串
- **Win32 平台**：检测 `uuid` 或 `info` 中包含 `win32`、`windows` 字符串

```python
# PlatformFactory.detect_platform() 内部逻辑
uuid = getattr(controller, 'uuid', None)
info = getattr(controller, 'info', None)
# 根据字符串匹配判断平台类型
```

### 按键跟踪

为支持安全停止功能，各平台维护活跃按键/触点集合：

- **Win32 平台**：`self._active_keys: set` - 跟踪已按下未释放的键码
- **ADB 平台**：`self._active_contacts: Dict[str, int]` - 跟踪已按下未释放的触点

### 工作流程

1. 框架启动时，自动扫描并注册所有动作
2. 根据控制器类型自动检测平台类型
3. 创建相应的平台实例
4. 解析操作序列，自动检测模式（普通/时间线）
5. 执行动作序列，调用平台方法
6. 返回执行结果

### 安全停止

执行过程中可响应停止通知，释放全部按键：

```python
# OperationExecutor.execute_timeline() 内部逻辑
while self._timeline.get_status()['is_running']:
    if context is not None and getattr(context.tasker, 'stopping', False):
        self._platform.release_all()  # 释放全部按键
        self._timeline.stop()
        return False
    self._timeline.update()
```

`PlatformBase.release_all()` 方法由各平台实现：

- **Win32**：遍历 `_active_keys`，调用 `post_key_up` 释放
- **ADB**：遍历 `_active_contacts`，调用 `post_touch_up` 释放

## 支持的动作类型

| 动作 | 说明 | 参数 |
| :--- | :--- | :--- |
| move | 移动 | direction (forward/backward/left/right), duration |
| jump | 跳跃 | 无 |
| dodge | 闪避/冲刺 | direction (可选) |
| turn | 转向 | angle |
| interact | 交互 | interaction_type |
| spiral_leap | 螺旋飞跃 | 无 |
| crouch | 下蹲 | 无 |
| charge_attack | 蓄力攻击 | duration, x, y |
| wait | 等待 | duration |

## 平台配置

### Win32 平台（键盘映射）

```json
{
  "win32": {
    "description": "Windows平台，使用键盘模拟",
    "key_mappings": {
      "forward": "W",
      "backward": "S",
      "left": "A",
      "right": "D",
      "jump": "Space",
      "interact": "F",
      "dodge": "Shift",
      "spiral_leap": "Q",
      "crouch": "C"
    }
  }
}
```

### ADB 平台（触摸坐标）

```json
{
  "adb": {
    "description": "ADB平台，使用触摸控制",
    "touch_positions": {
      "joystick_center": {"x": 195, "y": 551, "contact": 0},
      "jump_button": {"x": 980, "y": 410, "contact": 2},
      "sprint_button": {"x": 1200, "y": 360, "contact": 3},
      "interact_button": {"x": 730, "y": 355, "contact": 4},
      "spiral_leap_button": {"x": 1100, "y": 480, "contact": 5},
      "view_control_center": {"x": 1000, "y": 360, "contact": 1},
      "crouch_button": {"x": 850, "y": 450, "contact": 6},
      "charge_attack_button": {"x": 730, "y": 355, "contact": 7}
    },
    "generic_contact": 8
  }
}
```

触点配置说明：每个动作使用独立的触点ID，支持动作重叠执行。

## 时间线模式详解

时间线模式支持复杂的动作序列编排：

### 基本语法

```json
{
  "operations": [
    {
      "action": "动作名称",
      "params": {...},
      "duration": 持续时间(秒),
      "priority": 优先级(可选),
      "overlays": [
        {"action": "动作名称", "params": {...}, "at": 触发时间(秒)}
      ]
    }
  ],
  "loop_count": 循环次数
}
```

### 示例：复杂动作序列

```json
{
  "operations": [
    {"action": "move", "params": {"direction": "left"}, "duration": 2.0},
    {"action": "wait", "duration": 2.0},
    {
      "action": "move",
      "params": {"direction": "forward"},
      "duration": 8.0,
      "overlays": [{"action": "dodge", "params": {"direction": "forward"}, "at": 3.0}]
    },
    {
      "action": "move",
      "params": {"direction": "left"},
      "duration": 12.0,
      "overlays": [{"action": "jump", "at": 5.0}]
    }
  ],
  "loop_count": 1
}
```

## 类人化效果

框架内置类人化处理器，使动作更自然：

### 配置项

```json
{
  "humanization": {
    "enabled": true,
    "reaction_time_range_ms": [50, 200],
    "action_delay_range_ms": [30, 100],
    "smooth_move_enabled": true,
    "random_offset_enabled": true,
    "jitter_enabled": false
  }
}
```

### 效果说明

| 效果 | 说明 |
| :--- | :--- |
| 反应时间 | 随机延迟 50-200ms 后执行动作 |
| 动作间隔 | 动作之间添加 30-100ms 随机间隔 |
| 平滑移动 | 摇杆移动使用平滑插值 |
| 随机偏移 | 坐标添加微小随机偏移 |
| 抖动效果 | 模拟人手抖动（可选） |

## 最佳实践

- 动作设计：每个动作应该专注于单一功能
- 参数定义：在 JSON 中明确定义参数类型和默认值
- 平台实现：确保在所有支持的平台上都有实现
- 错误处理：在动作执行中添加适当的错误处理
- 时间线设计：使用 overlays 实现并发动作，避免动作冲突

## 平台扩展

要添加新的平台支持：

1. 创建平台目录：`platforms/new_platform/`
2. 创建平台类，继承自 `PlatformBase`
3. 实现所有抽象方法
4. 在 `PlatformFactory` 中注册平台类型
5. 在 `config/default.json` 中添加平台配置

## 故障排除

| 问题 | 解决方法 |
| :--- | :--- |
| 动作未注册 | 检查动作文件是否在正确目录，装饰器是否正确 |
| 参数验证失败 | 检查 JSON 配置中的参数定义 |
| 平台检测失败 | 确保控制器对象有正确的属性 |
| 动作执行失败 | 检查平台实现是否完整 |
| 触点冲突 | 确保每个动作使用独立的触点ID |

## 性能优化

- 动作缓存：频繁使用的动作会被缓存
- 延迟优化：根据平台特性调整动作延迟
- 批量执行：支持批量执行多个动作
- 测试模式：时间线支持跳过实际等待，加速测试

## 导出模块

```python
from OperationRecording import (
    # 数据类型
    Operation,
    OperationParam,
    # 核心组件
    OperationExecutor,
    OperationParser,
    ActionTimeline,
    TimedAction,
    ActionPriority,
    Humanizer,
    humanizer,
    # 动作基础
    ActionBase,
    ActionRegistry,
    action_registry,
    # MaaFramework 入口
    OperationRecordAction,
)
```
