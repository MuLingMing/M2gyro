# AutoPathFinding 自动寻路模块

## 1. 模块概述

### 1.1 功能定义

根据游戏截图识别指定目标图标，结合距离信息判断目标位置，自动执行移动操作到达目标点。

### 1.2 核心能力

- 目标图标识别（模板匹配）
- 距离信息读取（OCR）
- 多目标选择（接口化，可扩展）
- 自动移动（平台适配，复用 OperationRecording）
- 运动状态评估（到达 / 卡住 / 接近中）

### 1.3 技术栈

- **识别**：MaaFramework 内置 TemplateMatch + OCR
- **平台**：复用 OperationRecording 的 PlatformFactory
- **调度**：MaaFramework Pipeline
- **分辨率基准**：720p (1280x720)

---

## 2. 架构设计

### 2.1 组件架构

```
┌─────────────────────────────────────────────────────────┐
│                    Pipeline 协调层                       │
│  (JSON 定义识别流程、分支逻辑、任务调度)                 │
└─────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┴─────────────────┐
        ▼                                   ▼
┌─────────────────────┐           ┌─────────────────────┐
│  PathFindingReco    │           │  PathFinderAction   │
│  (Custom Recognition)│           │  (Custom Action)    │
├─────────────────────┤           ├─────────────────────┤
│ • 模板匹配识别目标   │           │ • 从 Reco 提取方向  │
│ • OCR 提取距离       │    ───►   │ • 调用 platform.move│
│ • 选择最优目标       │           │ • release_all 释放  │
│ • 计算移动方向       │           │                     │
│ • 评估运动状态       │           │                     │
└─────────────────────┘           └─────────────────────┘
        │                                   │
        └─────────────────┬─────────────────┘
                          ▼
                ┌─────────────────────┐
                │   PlatformFactory   │
                │ (OperationRecording) │
                └─────────────────────┘
                          │
                          ▼
                ┌─────────────────────┐
                │     Selector/       │
                │ (策略插件，可扩展)  │
                └─────────────────────┘
```

### 2.2 设计原则

- **Reco 职责**：根据截图返回信息（目标位置、距离、方向、运动状态）
- **Action 职责**：根据 Reco 返回的信息执行移动操作
- **选择器**：通过 `selector/` 目录下的可插拔类实现多目标选择策略
- **平台层**：复用 OperationRecording 的 PlatformFactory，不重复实现
- **卡住/到达检测**：由 PathFindingReco 跨帧跟踪并在 `detail.state` 中返回，Pipeline 根据状态决定分支；Action 内不做检测

### 2.3 组件清单

| 组件                        | 类型               | 职责                                                 |
| --------------------------- | ------------------ | ---------------------------------------------------- |
| **PathFindingReco**         | Custom Recognition | 识别目标、提取距离、计算方向、选择目标、评估运动状态 |
| **PathFinderAction**        | Custom Action      | 执行移动、释放按键                                   |
| **TargetSelector**          | Python 接口        | 目标选择策略（抽象基类）                             |
| **PriorityTargetSelector**  | 预置实现           | 按模板优先级选择                                     |
| **NearestTargetSelector**   | 预置实现           | 按距离最近选择                                       |
| **CompositeTargetSelector** | 预置实现           | 按类型优先级 + 距离组合选择                          |
| **PlatformFactory**         | 复用               | 平台操作适配（OperationRecording）                   |

---

## 3. 使用说明

### 3.1 快速开始

#### 3.1.1 注册组件

在 `agent/custom.json` 中注册组件（平铺格式）：

```json
{
    "PathFindingReco": {
        "type": "recognition",
        "class": "PathFindingReco",
        "file_path": "AutoPathFinding/recognition/path_finding_reco.py"
    },
    "PathFinderAction": {
        "type": "action",
        "class": "PathFinderAction",
        "file_path": "AutoPathFinding/action/path_finder_action.py"
    }
}
```

> 说明：`selector/` 目录下的类（`TargetSelector` / `PriorityTargetSelector` / `NearestTargetSelector` / `CompositeTargetSelector`）是 `PathFindingReco` 内部使用的 Python 模块，**不需要**在 `custom.json` 中注册。

#### 3.1.2 准备模板图片

将目标图标模板放入 `assets/resource/image/` 目录：

```
assets/resource/image/
├── quest_icon.png      # 任务图标
├── npc_icon.png        # NPC 图标
└── shop_icon.png       # 商店图标
```

### 3.2 PathFindingReco 参数

| 参数                       | 类型             | 默认值              | 说明                                                                      |
| -------------------------- | ---------------- | ------------------- | ------------------------------------------------------------------------- |
| `expected_templates`       | `list[str]`      | `[]`                | 期望匹配的模板列表（必填）                                                |
| `roi`                      | `list[int]`      | `[0, 0, 1280, 720]` | 识别区域 [x, y, w, h]                                                     |
| `threshold`                | `float`          | `0.8`               | 匹配阈值 (0-1)                                                            |
| `selector_type`            | `str`            | `"priority"`        | 选择器类型：`priority` / `nearest` / `composite`                          |
| `selector_priority`        | `list[int\|str]` | `[]`                | 选择器优先级（支持索引或名称格式）                                        |
| `distance_pattern`         | `str`            | `"(\d+)米"`         | 距离 OCR 正则表达式                                                       |
| `distance_offset`          | `list[int]`      | `[10, 10, 20, 20]`  | 距离 OCR 区域偏移 [left, top, right, bottom]                              |
| `distance_threshold`       | `float`          | `0.3`               | OCR 置信度阈值                                                            |
| `dead_zone`                | `int`            | `50`                | 方向判断死区（像素，欧氏距离），目标在死区内时返回 `direction="centered"` |
| `arrival_distance`         | `int`            | `30`                | 到达判定距离阈值（像素），OCR 距离 ≤ 此值时 `state="arrived"`             |
| `stuck_threshold`          | `int`            | `3`                 | 卡住判定连续帧数，连续达到此值时 `state="stuck"`                          |
| `stuck_distance_tolerance` | `int`            | `5`                 | 卡住距离容差（像素），相邻两帧距离缩短值 ≤ 此值视为无进展                 |
| `stuck_center_tolerance`   | `int`            | `10`                | 卡住中心偏移容差（像素），无距离信息时相邻两帧中心偏移 ≤ 此值视为无进展   |

#### 返回值格式

```python
# 命中目标
{
    "box": [x, y, w, h],           # 目标边界框
    "detail": {
        "hit": True,
        "hit_node": "if",          # 用于 IfElseAction 分支
        "target": {
            "template": "quest_icon.png",
            "center": [640.0, 360.0],  # 浮点坐标
            "bbox": [600, 320, 80, 80],
            "score": 0.95,
            "distance": 150            # 可选
        },
        "direction": "forward",        # forward/backward/left/right/centered
        "state": "approaching"         # approaching/arrived/stuck
    }
}

# 未命中目标
{
    "box": None,
    "detail": {
        "hit": False,
        "hit_node": "else"
    }
}
```

### 3.3 PathFinderAction 参数

| 参数                 | 类型  | 默认值 | 说明                                                      |
| -------------------- | ----- | ------ | --------------------------------------------------------- |
| `move_duration`      | `int` | `500`  | 无距离信息时的默认移动持续时间（毫秒）                    |
| `move_duration_far`  | `int` | `1500` | 远距离移动持续时间（毫秒），距离 ≥ `distance_far` 时使用  |
| `move_duration_near` | `int` | `300`  | 近距离移动持续时间（毫秒），距离 ≤ `distance_near` 时使用 |
| `distance_far`       | `int` | `200`  | 远距离阈值（像素）                                        |
| `distance_near`      | `int` | `50`   | 近距离阈值（像素）                                        |

距离在 `(distance_near, distance_far)` 之间时，移动时长按线性插值计算；`distance` 为 `None` 时回退到 `move_duration`。

### 3.4 选择器类型

#### 3.4.1 priority（按优先级选择）

按优先级顺序逐个识别，命中即停（短路求值）。

```json
{
    "selector_type": "priority",
    "expected_templates": [
        "quest_icon.png",
        "npc_icon.png"
    ]
}
```

#### 3.4.2 nearest（按距离选择）

全量识别所有模板，提取距离信息，选择距离最近的目标。

```json
{
    "selector_type": "nearest",
    "distance_pattern": "(\\d+)米",
    "distance_offset": [
        10,
        10,
        20,
        20
    ]
}
```

#### 3.4.3 composite（组合条件选择）

按优先级顺序识别，同优先级内选择距离最近的目标。

```json
{
    "selector_type": "composite",
    "expected_templates": [
        "quest_icon.png",
        "npc_icon.png"
    ],
    "distance_pattern": "(\\d+)米"
}
```

#### 3.4.4 selector_priority 参数

支持**索引格式**和**名称格式**两种写法，用于调整 `expected_templates` 的优先级顺序。

**索引格式**（0-based）：

```json
{
    "expected_templates": [
        "A",
        "B",
        "C"
    ],
    "selector_priority": [
        1,
        2
    ]
}
```

优先级：B > C > A

**名称格式**：

```json
{
    "expected_templates": [
        "A",
        "B",
        "C"
    ],
    "selector_priority": [
        "B",
        "C"
    ]
}
```

优先级：B > C > A

---

## 4. Pipeline 配置示例

> **提示**：完整示例中的 `selector_priority` 字段可省略，未设置时使用 `expected_templates` 原始顺序。

### 4.1 基础寻路

```json
{
    "AutoPathFinding": {
        "recognition": "Custom",
        "custom_recognition": "PathFindingReco",
        "custom_recognition_param": {
            "expected_templates": ["quest_icon.png"],
            "selector_type": "priority",
            "selector_priority": ["quest_icon.png"]
        },
        "next": ["PathFinderAction"]
    },
    "PathFinderAction": {
        "custom_action": "PathFinderAction",
        "custom_action_param": {
            "move_duration": 500
        },
        "next": ["AutoPathFinding"]
    }
}
```

### 4.2 带 IfElseAction 的条件分支

```json
{
    "AutoPathFinding": {
        "recognition": "Custom",
        "custom_recognition": "PathFindingReco",
        "custom_recognition_param": {
            "expected_templates": ["quest_icon.png"],
            "selector_type": "priority",
            "selector_priority": ["quest_icon.png"]
        },
        "next": ["HandlePathFinding"]
    },
    "HandlePathFinding": {
        "custom_action": "IfElseAction",
        "if": ["PathFinderAction"],
        "else": ["TaskComplete"]
    },
    "PathFinderAction": {
        "custom_action": "PathFinderAction",
        "next": ["AutoPathFinding"]
    },
    "TaskComplete": {
        "next": []
    }
}
```

### 4.3 多目标选择

```json
{
    "AutoPathFinding": {
        "recognition": "Custom",
        "custom_recognition": "PathFindingReco",
        "custom_recognition_param": {
            "expected_templates": [
                "quest_icon.png",
                "npc_icon.png",
                "shop_icon.png"
            ],
            "selector_type": "composite",
            "selector_priority": [
                "quest_icon.png",
                "npc_icon.png",
                "shop_icon.png"
            ]
        },
        "next": ["PathFinderAction"]
    },
    "PathFinderAction": {
        "custom_action": "PathFinderAction",
        "next": ["AutoPathFinding"]
    }
}
```

---

## 5. 数据类型定义

### 5.1 TargetInfo

```python
@dataclass
class TargetInfo:
    """识别到的目标信息"""
    template: str                      # 匹配的模板名称
    center: tuple[float, float]        # 中心坐标 (x, y)，浮点精度
    bbox: tuple[int, int, int, int]    # 边界框 (x, y, w, h)
    score: float                       # 匹配置信度
    distance: int | None = None        # 距离值（如果存在）
```

### 5.2 TargetSelector 接口

```python
class TargetSelector(ABC):
    """目标选择器接口"""

    @abstractmethod
    def select(self, targets: list[TargetInfo]) -> TargetInfo | None:
        """从目标列表中选择一个目标"""
        ...
```

---

## 6. 平台适配

### 6.1 复用 OperationRecording

直接使用 OperationRecording 的 PlatformFactory，无需重复实现。

```python
from OperationRecording.platforms import PlatformFactory
# ↑ 必须用包级导入（确保 OperationRecording.platforms 包被加载，
#   触发 @register_platform 装饰器执行，否则 platform_registry 为空）

# 创建平台实例（带缓存）
platform = PlatformFactory.create_from_config({}, context.tasker.controller)

# 使用平台操作
platform.move("forward", duration=0.5)  # 移动
platform.turn(angle)                     # 调整视角
platform.click(x, y)                     # 点击屏幕
platform.release_all()                   # 释放所有操作
```

**平台缓存**：`create_from_config` 内部使用 `WeakKeyDictionary` 缓存 platform 实例，同一 controller 多次调用返回同一 platform，避免高频调用时的重复创建并保留 platform 内部状态（`_active_contacts`、`_active_directions`）。测试或重连场景可调用 `PlatformFactory.clear_cache()` 显式清空。

### 6.2 可用的平台操作

| OperationRecording 方法              | AutoPathFinding 用途                                         |
| ------------------------------------ | ------------------------------------------------------------ |
| `platform.move(direction, duration)` | 移动角色（forward/backward/left/right），`centered` 时不调用 |
| `platform.turn(angle)`               | 调整视角使目标居中                                           |
| `platform.click(x, y)`               | 点击屏幕目标位置                                             |
| `platform.swipe(...)`                | 滑动操作                                                     |
| `platform.release_all()`             | 释放所有操作                                                 |

---

## 7. 识别流程详解

### 7.1 统一识别流程

```
┌─────────────────────────────────────────────────────────┐
│  1. 解析参数                                             │
│     - expected_templates: 模板列表                       │
│     - selector_priority: 计算最终优先级顺序               │
│     - selector_type: 选择器类型                          │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  2. 按优先级顺序识别                                     │
│     - priority: 短路识别（命中即停）                      │
│     - nearest: 全量识别                                  │
│     - composite: 全量识别（按优先级分组）                  │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  3. 距离提取（命中即提取）                                │
│     - 对命中结果的 box 扩大 distance_offset              │
│     - 识别 OCR，匹配 distance_pattern                    │
│     - 绑定距离到 TargetInfo                              │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  4. 选择目标                                             │
│     - 通过 selector/ 目录下的选择器类                    │
│     - priority: 返回第一个命中的                         │
│     - nearest: 返回距离最近的                            │
│     - composite: 返回当前优先级中距离最近的               │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  5. 计算方向                                             │
│     - 角度分箱 + 圆形死区                                 │
│     - 返回 forward/backward/left/right/centered         │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  6. 评估运动状态                                         │
│     - 跨帧跟踪目标距离与中心位置                          │
│     - 返回 approaching / arrived / stuck                │
└─────────────────────────────────────────────────────────┘
```

### 7.2 目标识别

**方案**：使用 MaaFramework 内置 `run_recognition_direct` API。

```python
def _match_template(self, context, img, template_name, roi, threshold):
    """单个模板匹配"""
    reco_param = JTemplateMatch(
        template=[template_name],
        roi=roi,
        threshold=[threshold],
        green_mask=True,   # 过滤绿色高亮区域（任务追踪标记）
    )
    reco_detail = context.run_recognition_direct(
        JRecognitionType.TemplateMatch,
        reco_param,
        img,
    )

    if reco_detail is not None and reco_detail.hit:
        best_result = reco_detail.best_result
        if isinstance(best_result, TemplateMatchResult):
            box = best_result.box
            if box is not None:
                # 兼容 box 为 Rect 对象或 list [x, y, w, h]
                if isinstance(box, (list, tuple)):
                    x, y, w, h = box[0], box[1], box[2], box[3]
                else:
                    x, y, w, h = box.x, box.y, box.w, box.h
                # 浮点除法，避免 1 像素抖动
                center = (x + w / 2, y + h / 2)
                return TargetInfo(
                    template=template_name,
                    center=center,
                    bbox=(x, y, w, h),
                    score=best_result.score,
                )

    return None
```

### 7.3 距离提取

**方案**：使用可配置的正则表达式和偏移量。

```python
def _extract_distance(self, context, img, target, param):
    """提取目标下方的距离信息"""
    import re

    distance_pattern = param.distance_pattern
    distance_offset = param.distance_offset
    distance_threshold = param.distance_threshold

    # 计算 OCR 识别区域（基于 box 扩展 offset）
    x, y, w, h = target.bbox
    left, top, right, bottom = distance_offset
    roi = (
        max(0, x - left),
        max(0, y - top),
        w + left + right,
        h + top + bottom,
    )

    try:
        reco_param = JOCR(
            expected=[distance_pattern],
            roi=roi,
            threshold=distance_threshold,
        )
        reco_detail = context.run_recognition_direct(
            JRecognitionType.OCR,
            reco_param,
            img,
        )

        if reco_detail is not None and reco_detail.hit:
            best_result = reco_detail.best_result
            if isinstance(best_result, OCRResult):
                text = best_result.text
                if text:
                    match = re.search(distance_pattern, text)
                    if match:
                        distance_str = match.group(1)
                        if distance_str.isdigit():
                            return TargetInfo(
                                template=target.template,
                                center=target.center,
                                bbox=target.bbox,
                                score=target.score,
                                distance=int(distance_str),
                            )
    except Exception:
        pass

    return target
```

### 7.4 方向计算

**方案**：角度分箱（angular binning）+ 圆形死区（circular dead zone）

相比轴向比较，角度分箱更稳定（避免 1 像素抖动）；圆形死区比矩形死区更自然（角落无鬼影区）。

```python
import math

def _calculate_direction(self, target_center, dead_zone):
    """计算移动方向（forward/backward/left/right/centered）"""
    tx, ty = target_center
    cx, cy = SCREEN_CENTER  # (640, 360)

    dx = tx - cx
    dy = ty - cy

    # 1. 圆形死区：欧氏距离（比矩形死区更自然）
    # 目标已在屏幕中心死区内，无需移动
    if math.hypot(dx, dy) <= dead_zone:
        return "centered"

    # 2. 角度分箱：用 -dy 翻转以匹配游戏方向（屏幕上方 = forward）
    angle = math.degrees(math.atan2(-dy, dx))

    # 角度分箱规则：
    #   -45° ≤ angle <   45° → right   （目标在右）
    #    45° ≤ angle <  135° → forward （目标在上）
    #   135° ≤ angle <  180° 或 -180° ≤ angle < -135° → left  （目标在左）
    #  -135° ≤ angle <  -45° → backward（目标在下）
    if -45 <= angle < 45:
        return "right"
    elif 45 <= angle < 135:
        return "forward"
    elif angle >= 135 or angle < -135:
        return "left"
    else:  # -135 <= angle < -45
        return "backward"
```

### 7.5 运动状态检测

**方案**：由 PathFindingReco 在识别阶段跨帧跟踪目标状态，并通过 `detail.state` 返回。

状态定义：

- `approaching`：正在接近目标（默认状态）
- `arrived`：OCR 距离 ≤ `arrival_distance`，判定已到达
- `stuck`：连续 `stuck_threshold` 帧距离/中心几乎无变化，判定卡住

判定逻辑（伪代码）：

```python
def _evaluate_movement_state(self, node_name, selected, param):
    distance = selected.distance
    if distance is not None and distance <= param.arrival_distance:
        # 到达目标，清空该节点历史状态
        self._path_state.pop(node_name, None)
        return "arrived"

    prev = self._path_state.get(node_name, {})
    last_distance = prev.get("last_distance")
    last_center = prev.get("last_center")
    stuck_count = prev.get("stuck_count", 0)

    if self._is_stuck(selected, last_distance, last_center, param):
        stuck_count += 1
    else:
        stuck_count = 0

    self._path_state[node_name] = {
        "last_distance": selected.distance,
        "last_center": selected.center,
        "stuck_count": stuck_count,
    }

    if stuck_count >= param.stuck_threshold:
        return "stuck"
    return "approaching"
```

跨帧状态按 `node_name` 隔离，生命周期跟随 Python 进程。到达目标时会自动清空对应状态，避免切换节点后历史数据污染。

### 7.6 状态处理

PathFindingReco 返回的 `detail.state` 可与 Pipeline 分支配合使用，典型用法：

```json
{
    "AutoPathFinding": {
        "recognition": "Custom",
        "custom_recognition": "PathFindingReco",
        "next": ["HandleState"]
    },
    "HandleState": {
        "custom_action": "IfElseAction",
        "custom_action_param": {
            "if": ["ArrivedHandler"],
            "else": ["PathFinderAction"]
        }
    }
}
```

> 说明：IfElseAction 默认按 `hit_node` 分支（命中目标为 `if`，未命中为 `else`）。如需按 `state` 分支，需要自定义 Action 读取 `reco_detail.best_result.detail.state`。

**处理建议**：

- `arrived`：结束寻路，执行后续任务（如交互、进入副本）
- `stuck`：尝试脱卡（如释放方向键、跳一下、切换路径）
- `approaching`：继续执行 `PathFinderAction` 移动

---

## 8. 文件结构

```
agent/AutoPathFinding/
├── __init__.py                     # 模块初始化
├── README.md                       # 本文档
├── action/
│   ├── __init__.py
│   ├── param.py                    # PathFinderAction 参数数据类
│   └── path_finder_action.py       # 自定义动作：执行移动
├── recognition/
│   ├── __init__.py
│   ├── param.py                    # PathFindingReco 参数数据类
│   └── path_finding_reco.py        # 自定义识别：识别目标
└── selector/
    ├── __init__.py
    ├── base.py                     # TargetSelector 接口
    ├── types.py                    # TargetInfo 数据类型
    ├── priority_selector.py        # 按优先级选择
    ├── nearest_selector.py         # 按距离选择
    └── composite_selector.py       # 组合条件选择
```

---

## 9. 扩展指南

### 9.1 自定义选择器

实现 `TargetSelector` 接口即可：

```python
from agent.AutoPathFinding.selector import TargetSelector, TargetInfo

class MyCustomSelector(TargetSelector):
    def select(self, targets: list[TargetInfo]) -> TargetInfo | None:
        # 自定义选择逻辑
        ...
```

### 9.2 集成 OCR

在 `PathFindingReco._extract_distance` 方法中使用 MaaFramework 内置 OCR：

```python
def _extract_distance(self, context, img, target, param):
    """使用 MaaFramework 内置 OCR 提取目标下方的距离信息"""
    import re

    x, y, w, h = target.bbox
    left, top, right, bottom = param.distance_offset
    roi = (
        max(0, x - left),
        max(0, y - top),
        w + left + right,
        h + top + bottom,
    )

    try:
        reco_param = JOCR(
            expected=[param.distance_pattern],
            roi=roi,
            threshold=param.distance_threshold,
        )
        reco_detail = context.run_recognition_direct(
            JRecognitionType.OCR,
            reco_param,
            img,
        )

        if reco_detail is not None and reco_detail.hit:
            best_result = reco_detail.best_result
            if isinstance(best_result, OCRResult):
                text = best_result.text
                if text:
                    match = re.search(param.distance_pattern, text)
                    if match and match.group(1).isdigit():
                        return TargetInfo(
                            template=target.template,
                            center=target.center,
                            bbox=target.bbox,
                            score=target.score,
                            distance=int(match.group(1)),
                        )
    except Exception:
        pass

    return target
```

---

## 10. API 接口规范

### 10.1 Custom Recognition 接口规范

**PathFindingReco** 遵循 MaaFramework Custom Recognition 规范：

```python
class PathFindingReco(CustomRecognition):
    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> Union[CustomRecognition.AnalyzeResult, Optional[RectType]]:
        """
        参数:
        - context: MaaFramework 上下文对象
        - argv: 识别参数，包含 image、roi、custom_recognition_param 等

        返回值:
        - CustomRecognition.AnalyzeResult: 识别结果
        - Optional[RectType]: 识别到的位置
        - None: 识别失败
        """
```

**关键 API 使用**：

- `argv.image`: 获取输入图片
- `argv.custom_recognition_param`: 获取自定义参数（JSON 字符串或 dict）
- `context.run_recognition_direct()`: 调用 MaaFramework 内置识别器（TemplateMatch、OCR 等）
- `CustomRecognition.AnalyzeResult(box=..., detail={...})`: 返回识别结果

**RecognitionDetail 类型安全访问**：

`context.run_recognition_direct()` 返回 `RecognitionDetail`，其 `best_result` 是联合类型，需要根据算法类型进行类型检查：

```python
from maa.define import TemplateMatchResult, OCRResult

# TemplateMatch 结果
reco_detail = context.run_recognition_direct(JRecognitionType.TemplateMatch, reco_param, img)
if reco_detail is not None and reco_detail.hit:
    best_result = reco_detail.best_result
    if isinstance(best_result, TemplateMatchResult):
        box = best_result.box   # Rect 或 list
        score = best_result.score  # float

# OCR 结果
reco_detail = context.run_recognition_direct(JRecognitionType.OCR, reco_param, img)
if reco_detail is not None and reco_detail.hit:
    best_result = reco_detail.best_result
    if isinstance(best_result, OCRResult):
        text = best_result.text  # str
        score = best_result.score  # float
```

**RecognitionResult 联合类型**：

- `TemplateMatchResult`: box, score
- `OCRResult`: box, score, text
- `FeatureMatchResult`: box, count
- `CustomRecognitionResult`: box, detail

### 10.2 Custom Action 接口规范

**PathFinderAction** 遵循 MaaFramework Custom Action 规范：

```python
class PathFinderAction(CustomAction):
    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        """
        参数:
        - context: MaaFramework 上下文对象
        - argv: 运行参数，包含识别结果和自定义参数

        返回值:
        - CustomAction.RunResult: 执行结果
        """
```

**关键 API 使用**：

- `argv.custom_action_param`: 获取自定义参数（JSON 字符串）
- `argv.reco_detail.best_result.detail`: 获取前序识别器返回的 detail 字典
- `context.tasker.stopping`: 检查是否收到停止信号
- `context.tasker.controller`: 获取控制器（用于 platform 创建）
- `CustomAction.RunResult(success=True/False)`: 返回执行结果

### 10.3 与 IfElseAction 集成

PathFindingReco 返回的 `detail` 字典包含 `hit_node` 字段，可与 IfElseAction 配合使用：

```json
{
    "AutoPathFinding": {
        "recognition": "Custom",
        "custom_recognition": "PathFindingReco",
        "custom_recognition_param": {
            "expected_templates": ["quest_icon.png"],
            "selector_type": "priority",
            "selector_priority": ["quest_icon.png"]
        },
        "action": "Custom",
        "custom_action": "IfElseAction",
        "custom_action_param": {
            "if": ["PathFinderAction"],
            "else": ["TaskComplete"]
        }
    }
}
```

**返回值映射**：

- `hit=True, hit_node="if"` → IfElseAction 执行 `if` 分支
- `hit=False, hit_node="else"` → IfElseAction 执行 `else` 分支

---

## 11. 风险评估

| 风险                         | 概率 | 影响 | 应对措施                                             |
| ---------------------------- | ---- | ---- | ---------------------------------------------------- |
| 模板匹配误识别               | 中   | 中   | 动态阈值 + `green_mask` 过滤任务追踪标记             |
| OCR 识别不准确               | 中   | 中   | 正则匹配 + `isdigit` 容错处理                        |
| 1 像素抖动导致方向频繁切换   | 低   | 中   | 角度分箱 + 圆形死区（`math.hypot`）                  |
| 目标在死区内仍继续前进       | 低   | 中   | 死区内返回 `direction="centered"`，Action 不执行移动 |
| 平台操作不兼容               | 低   | 高   | 复用 OperationRecording，已验证                      |
| 平台实例重复创建             | 低   | 中   | `PlatformFactory` 内部 `WeakKeyDictionary` 缓存      |
| 距离缺失导致卡住误判         | 低   | 中   | 无距离时回退到中心偏移判断                           |
| 到达阈值设置不当导致提前结束 | 低   | 中   | 按实际游戏距离调整 `arrival_distance`                |

---

## 12. 参考资料

- [MaaFramework Pipeline 协议](https://github.com/MaaXYZ/MaaFramework/blob/main/docs/en_us/3.1-PipelineProtocol.md)
- [MaaFramework Custom Recognition/Action](https://github.com/MaaXYZ/MaaFramework/blob/main/docs/en_us/3.2-CustomAction.md)
- [OperationRecording 模块](../OperationRecording/)
