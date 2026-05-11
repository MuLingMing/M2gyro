# OperationRecording 操作录制组件

## 简介

`OperationRecording` 是基于 MaaFramework 的操作录制与回放组件。它支持：

- **普通模式**：顺序执行操作列表
- **时间线模式**：复杂动作序列、并行动作叠加、类人化效果
- **自动模式检测**：根据输入格式自动选择执行模式
- **统一模块化模板平台**：ModuleRegistry 泛型基类，Action/Effect/Platform 三种模块类型完全对称
- **平台家族继承**：KeyboardPlatform/TouchPlatform 家族基类，子类仅需提供映射表

## 版本

当前版本：**v3.0.0**

## 架构概览

```
OperationRecording/
├── __init__.py                    # 模块入口，统一导出
├── registry.py                    # ModuleRegistry[T] 泛型注册表基类
├── actions/                       # 动作模块（模板实例 A）
│   ├── __init__.py                # base + registry + basic/advanced
│   ├── base.py                    # ActionBase + TimelineMeta
│   ├── registry.py                # ActionRegistry + @register_action + action_registry
│   ├── operation_record_action.py # MaaFW CustomAction 入口
│   ├── basic/                     # 基础动作
│   │   ├── move_action.py
│   │   ├── jump_action.py
│   │   ├── dodge_action.py
│   │   ├── turn_action.py
│   │   ├── interact_action.py
│   │   ├── charge_attack_action.py
│   │   ├── crouch_action.py
│   │   ├── wait_action.py
│   │   ├── run_node_action.py
│   │   ├── swipe_action.py
│   │   ├── click_action.py
│   │   └── press_key_action.py
│   └── advanced/                  # 高级动作
│       └── spiral_leap_action.py
├── effects/                       # 效果插件模块（模板实例 B）
│   ├── __init__.py                # base + registry + builtin
│   ├── base.py                    # EffectBase 抽象基类
│   ├── registry.py                # EffectRegistry + @register_effect + effect_registry
│   ├── manager.py                 # EffectManager 效果管理器
│   └── builtin/                   # 内置效果插件
│       ├── acceleration.py
│       ├── random_delay.py
│       ├── human_timing.py
│       ├── reaction_delay.py
│       └── fatigue.py
├── platforms/                     # 平台模块（模板实例 C）
│   ├── __init__.py                # base + registry + desktop/adb
│   ├── base.py                    # PlatformBase 抽象基类
│   ├── keyboard.py                # KeyboardPlatform 键盘平台家族基类
│   ├── touch.py                   # TouchPlatform 触控平台家族基类
│   ├── registry.py                # PlatformRegistry + @register_platform + platform_registry
│   ├── factory.py                 # PlatformFactory 平台工厂
│   ├── desktop/                   # 桌面平台
│   │   ├── __init__.py
│   │   └── desktop_platform.py
│   └── adb/                       # ADB 平台
│       ├── __init__.py
│       └── adb_platform.py
├── core/                          # 核心调度层（不随模块扩展修改）
│   ├── __init__.py
│   ├── executor.py                # OperationExecutor 执行器
│   ├── parser.py                  # OperationParser 解析器
│   ├── timeline.py                # ActionTimeline + TimedAction + ActionPriority + ActionState
│   ├── types.py                   # Operation + OperationParam 数据结构
│   └── config.py                  # ConfigManager 配置管理器
└── config/
    └── default.json               # 默认配置
```

## 统一模块化模板平台

三种模块类型完全对称，遵循同一模板：

```
模块类型/
├── __init__.py          # 导入 base + registry + 子包触发注册
├── base.py              # 基类定义
├── registry.py          # 注册表(ModuleRegistry子类) + 装饰器 + 全局实例
└── 子包/
    ├── __init__.py      # 导入所有模块触发注册
    └── *.py             # 各模块实现，使用 @register_xxx("name") 注册
```

### ModuleRegistry 泛型基类

```python
from OperationRecording.registry import ModuleRegistry

class ModuleRegistry(Generic[T]):
    def register(self, name: str, cls: Type[T]) -> None: ...
    def unregister(self, name: str) -> None: ...
    def get(self, name: str) -> Optional[Type[T]]: ...
    def create(self, name: str, *args, **kwargs) -> Optional[T]: ...
    def list_modules(self) -> List[str]: ...
    def has(self, name: str) -> bool: ...
```

### 三种注册表完全对称

| 注册表 | 基类 | 装饰器 | 实例 |
|--------|------|--------|------|
| `ActionRegistry` | `ModuleRegistry[ActionBase]` | `@register_action("name")` | `action_registry` |
| `EffectRegistry` | `ModuleRegistry[EffectBase]` | `@register_effect("name")` | `effect_registry` |
| `PlatformRegistry` | `ModuleRegistry[PlatformBase]` | `@register_platform("name")` | `platform_registry` |

## TimelineMeta 声明式调度

每个 Action 类通过 `timeline_meta` 类属性声明其时间线行为，时间线调度逻辑自动根据此元数据决定调用方式：

```python
@dataclass
class TimelineMeta:
    has_duration: bool = False
    release_method: str | None = None
```

### 调度规则

| 条件 | 调用方式 |
|------|----------|
| `has_duration=True` + `duration > 0` | 调用 `start(params)` → 等待 → `release_action(release_method)` |
| `has_duration=True` + `duration = 0` | 仅调用 `start(params)`（按下不释放） |
| `has_duration=False` | 调用 `execute(params)`（瞬时完成） |

### 示例

```python
@register_action("move")
class MoveAction(ActionBase):
    timeline_meta = TimelineMeta(has_duration=True, release_method="move")

    def execute(self, params): return self._platform.move(params.get("direction", "forward"), params.get("duration", 1.0))
    def start(self, params): return self._platform.move(params.get("direction", "forward"), 0)

@register_action("jump")
class JumpAction(ActionBase):
    timeline_meta = TimelineMeta(has_duration=False)

    def execute(self, params): return self._platform.jump()
```

**不再需要修改**：`timeline.py`、`executor.py`、`parser.py`

## 平台家族继承体系

平台层采用家族基类模式，子类仅需提供映射表即可获得完整实现：

```
PlatformBase (抽象基类)
├── KeyboardPlatform (键盘家族基类)
│   └── DesktopPlatform (Windows 桌面)
└── TouchPlatform (触控家族基类)
    └── AdbPlatform (Android ADB)
```

### KeyboardPlatform

子类需提供：
- `_key_codes: Dict[str, int]` — 按键名到虚拟键码的映射
- `_action_key_map: Dict[str, List[str]]` — 动作名到按键名列表的映射（用于 `release_action()`）

```python
@register_platform("desktop")
class DesktopPlatform(KeyboardPlatform):
    _key_codes = {"W": 0x57, "A": 0x41, "S": 0x53, "D": 0x44, "Space": 0x20, ...}
    _action_key_map = {"move": ["W", "A", "S", "D"], "crouch": ["C"], "charge_attack": ["MouseLeft"]}
```

### TouchPlatform

子类需提供：
- `_touch_positions: Dict[str, Dict]` — 按钮位置配置（格式：`{"button_name": {"x": int, "y": int, "contact": int, ...}}`）
- `_generic_contact: int` — 通用触点 ID

```python
@register_platform("adb")
class AdbPlatform(TouchPlatform):
    _touch_positions = {
        "joystick_center": {"x": 225, "y": 536, "contact": 0, "joystick_run_offset": -60},
        "jump_button": {"x": 978, "y": 410, "contact": 1},
        ...
    }
    _generic_contact = 8
```

### 状态跟踪

| 平台家族 | 状态跟踪 | 类型 |
|----------|----------|------|
| KeyboardPlatform | `_active_keys` | `set` — 当前按下的键码集合 |
| TouchPlatform | `_active_contacts` | `Dict[str, int]` — contact_name → contact_id 映射 |

### 释放机制

- **`release_action(action_name)`**：根据动作名释放对应按键/触点
  - KeyboardPlatform：通过 `_action_key_map` 查找按键列表，发送 `post_key_up`
  - TouchPlatform：`"move"` 调用 `_joystick_center()` 归位摇杆，其他从 `_active_contacts` 查找并 `post_touch_up`
- **`release_all()`**：释放所有活跃按键/触点，清空状态跟踪

## ActionState 状态机

时间线模式下每个动作经历以下状态：

```
SCHEDULED → RUNNING → COMPLETED
                   ↘ CANCELLED（释放失败时）
```

| 状态 | 值 | 说明 |
|------|---|------|
| `SCHEDULED` | 1 | 已计划，等待开始时间 |
| `RUNNING` | 2 | 运行中 |
| `PAUSED` | 3 | 已暂停（预留） |
| `COMPLETED` | 4 | 已完成 |
| `CANCELLED` | 5 | 已取消（`release_action()` 失败时标记） |

## 动作参考

### 基础动作

| 动作名 | 类型 | 参数 | 说明 |
|--------|------|------|------|
| `move` | 持续 | `direction`: forward/backward/left/right, `duration`: 秒 | 移动，`release_method="move"` |
| `crouch` | 持续 | `duration`: 秒 | 下蹲，`release_method="crouch"` |
| `charge_attack` | 持续 | `duration`: 秒, `x`/`y`: 可选坐标 | 蓄力攻击，`release_method="charge_attack"` |
| `jump` | 瞬时 | — | 跳跃 |
| `dodge` | 瞬时 | `direction`: 可选方向 | 闪避 |
| `turn` | 瞬时 | `angle`: 角度（正右负左） | 转向 |
| `interact` | 瞬时 | `interaction_type`: 交互类型 | 交互 |
| `swipe` | 瞬时 | `start_x/y`, `end_x/y`, `duration` | 滑动 |
| `click` | 瞬时 | `x`, `y` | 点击 |
| `press_key` | 瞬时 | `key`: 按键名, `duration`: 秒 | 按键 |
| `wait` | 瞬时 | `duration`: 秒 / `until`: 绝对时间点 | 等待（仅时间线模式） |
| `run_node` | 瞬时 | `node`: 节点名, `blocking`: 是否阻塞 | 执行 Pipeline 节点 |

### 高级动作

| 动作名 | 类型 | 参数 | 说明 |
|--------|------|------|------|
| `spiral_leap` | 瞬时 | — | 螺旋飞跃 |

### 通用时间线参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `duration` | float | 动作持续时间（秒），顶层参数 |
| `overlays` | list | 叠加动作列表，每个包含 `action`/`params`/`at` |

## 新增模块标准流程

### 新增 Action

1. 在 `actions/basic/` 或 `actions/advanced/` 下创建新文件
2. 继承 `ActionBase`，声明 `timeline_meta`
3. 使用 `@register_action("action_name")` 注册
4. 在对应 `__init__.py` 中导入触发注册
5. 在 `platforms/desktop/` 和 `platforms/adb/` 中实现平台方法
6. 更新 Schema

```python
from ..base import ActionBase, TimelineMeta
from ..registry import register_action

@register_action("my_action")
class MyAction(ActionBase):
    timeline_meta = TimelineMeta(has_duration=True, release_method="my_action")

    def execute(self, params: dict) -> bool:
        return self._platform.my_action(params.get("target"))

    def start(self, params: dict) -> bool:
        return self._platform.my_action(params.get("target"))
```

**不再需要修改**：`timeline.py`、`executor.py`、`parser.py`

### 新增 Effect

1. 在 `effects/builtin/` 下创建新文件
2. 继承 `EffectBase`，实现 `apply()` 接口
3. 使用 `@register_effect("my_effect")` 注册
4. 在 `effects/builtin/__init__.py` 中导入触发注册
5. 在 `config/default.json` 的 `effects.plugins` 中添加配置

```python
from ..base import EffectBase
from ..registry import register_effect

@register_effect("my_effect")
class MyEffect(EffectBase):
    name: ClassVar[str] = "my_effect"

    def __init__(self, config=None):
        super().__init__(config)
        self._factor = self._config.get("factor", 0.1)

    def apply(self, action_name: str, params: dict, context: dict) -> dict:
        return params
```

**不再需要修改**：任何核心文件

### 新增 Platform

**类型 A（依赖家族基类）**：继承 KeyboardPlatform 或 TouchPlatform，仅需提供映射表。

```python
from ..keyboard import KeyboardPlatform
from ..registry import register_platform

@register_platform("my_desktop")
class MyDesktopPlatform(KeyboardPlatform):
    _key_codes = {"W": 0x57, ...}
    _action_key_map = {"move": ["W", "A", "S", "D"], ...}
```

**类型 B（全新平台）**：继承 PlatformBase，实现所有抽象方法。

```python
from ..base import PlatformBase
from ..registry import register_platform

@register_platform("my_platform")
class MyPlatform(PlatformBase):
    def click(self, x, y) -> bool: ...
    def swipe(self, sx, sy, ex, ey, dur) -> bool: ...
    def press_key(self, key, dur) -> bool: ...
    def release_key(self, key) -> bool: ...
    def release_all(self) -> bool: ...
```

**不再需要修改**：`factory.py`、`executor.py`、任何核心文件

## 效果插件系统

拟人化等效果通过插件系统管理，遵循开闭原则。每个效果插件可独立 `enabled` 控制。

### 内置插件

| 插件 | 功能 | 默认状态 | Config 字段 |
|------|------|----------|-------------|
| `acceleration` | 加减速效果 | 启用 | `actions`, `factor` |
| `random_delay` | 随机延迟 | 启用 | `actions`, `min_ms`, `max_ms`, `gap_min_ms`, `gap_max_ms` |
| `human_timing` | 时序微变 | 启用 | `duration_variance`, `wait_variance`, `min_duration_ms` |
| `reaction_delay` | 反应延迟 | 禁用 | `min_ms`, `max_ms` |
| `fatigue` | 疲劳模拟 | 禁用 | `threshold`, `factor`, `base_min_ms`, `base_max_ms` |

### 效果钩子

| 方法 | 调用时机 | 用途 |
|------|----------|------|
| `pre_action()` | 动作执行前 | 添加延迟（如反应时间、疲劳） |
| `apply()` | 参数处理时 | 修改参数（如加减速标记、随机延迟值） |
| `post_action()` | 动作执行后 | 后处理（预留） |

### 配置示例

```json
{
    "effects": {
        "enabled": true,
        "plugins": {
            "acceleration": {
                "enabled": true,
                "actions": ["move"],
                "factor": 0.15
            },
            "random_delay": {
                "enabled": true,
                "actions": ["jump"],
                "min_ms": 20,
                "max_ms": 80
            }
        }
    }
}
```

## 时间线模式

时间线模式支持复杂动作序列，包括并行动作叠加。自动检测条件：`operations` 中任一项包含 `duration` 或 `overlays` 字段（顶层或 `params` 中）。

### 参数格式

```json
{
    "operations": [
        {
            "action": "move",
            "params": {
                "direction": "left",
                "duration": 0,
                "acceleration": true,
                "overlays": [
                    {
                        "action": "turn",
                        "params": { "angle": 45.0 },
                        "at": 0.3
                    }
                ]
            },
            "duration": 2.0
        }
    ],
    "loop_count": 1
}
```

### Wait 动作

```json
{"action": "wait", "params": {"duration": 1.0}}
{"action": "wait", "params": {"until": 5.0}}
```

- `duration`：相对等待时长
- `until`：绝对时间点（相对于时间线开始），如果当前时间已超过则不等待

### 停止响应

时间线执行过程中检查 `context.tasker.stopping`，收到停止信号时：
1. 调用 `platform.release_all()` 释放所有按键/触点
2. 调用 `timeline.stop()` 停止时间线
3. 返回 `False`

## 平台支持

### 桌面平台（Desktop）

- 继承 `KeyboardPlatform`，使用键盘模拟
- 自动检测条件：控制器名称包含 `win32` 或 `desktop`
- 状态跟踪：`_active_keys`（键码集合）

### ADB 平台（Android）

- 继承 `TouchPlatform`，使用触摸控制
- 自动检测条件：控制器名称包含 `adb` 或 `android`
- 状态跟踪：`_active_contacts`（contact_name → contact_id）
- 分辨率基准：**720p (1280x720)**，所有坐标基于此分辨率

### 平台检测

`PlatformFactory.detect_platform()` 通过 `controller.name` 和 `controller.config` 自动判断平台类型，默认回退到 `"adb"`。

## 配置管理

`ConfigManager` 支持点分隔键路径访问：

```python
cm = ConfigManager()
cm.get("effects.enabled")           # True
cm.get("effects.plugins.acceleration.factor")  # 0.15
cm.get("nonexistent.key", "default")  # "default"
cm.set("effects.enabled", False)
cm.save("path/to/config.json")
```

## 使用示例

### Pipeline JSON 调用

```json
{
    "custom_action": "OperationRecordAction",
    "custom_action_param": {
        "operations": [
            {"action": "move", "params": {"direction": "forward", "duration": 1.0}},
            {"action": "jump", "params": {}}
        ],
        "loop_count": 1
    }
}
```

### Python API 调用

```python
from maa.context import Context
from OperationRecording import OperationExecutor

def run_operations(context: Context):
    executor = OperationExecutor(context)

    # 普通模式
    from OperationRecording import OperationParam
    param = OperationParam(operations=[...], loop_count=1)
    executor.execute(param)

    # 时间线模式
    sequence = [
        {"action": "move", "params": {"direction": "left", "duration": 1.0}, "duration": 2.0},
        {"action": "jump", "params": {}},
        {"action": "wait", "params": {"duration": 0.5}},
    ]
    executor.execute_timeline(sequence, loop_count=1)

    # 统一入口（自动检测模式）
    executor.execute_unified({"operations": [...], "loop_count": 1})
```

## 依赖

- Python 3.10+
- MaaFramework
