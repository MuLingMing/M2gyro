# AutoPathFinding 自动寻路模块设计方案

## 1. 概述

### 1.1 功能目标

识别场景中的目的地标志（门/菱形），控制角色自动移动到目标位置，支持多种目标选择策略和到达判定条件。

### 1.2 适用平台

| 平台 | 移动方式 | 视角调整 |
|------|----------|----------|
| ADB（Android） | 滑动虚拟摇杆 | 滑动屏幕让目标居中 |
| Win32（PC） | 方向键（预留） | 鼠标视角（预留） |

### 1.3 模块架构

```
agent/AutoPathFinding/
├── __init__.py              # 模块导出
├── recognition/
│   └── PathTargetReco.py    # 目标识别器
├── action/
│   └── AutoPathAction.py    # 寻路动作器
└── README.md                # 本文档
```

**职责分离**：

| 组件 | 类型 | 职责 |
|------|------|------|
| `PathTargetReco` | Custom Recognition | 识别所有可见目标，执行选择策略，返回最优目标 |
| `AutoPathAction` | Custom Action | 根据目标位置控制移动方向、调整视角、处理障碍物 |

---

## 2. 目的地标志定义

### 2.1 目标类型

#### 组 A：门类标志（互斥，不会与组 B 同时出现）

| 类型 ID | 名称 | 视觉特征 | 优先级参考 |
|---------|------|----------|-----------|
| `gold_door` | 金色门 | 金色发光门框 | 高（策略1优先） |
| `blue_door` | 蓝色门 | 蓝色发光门框 | 高（策略1优先） |
| `red_sword_door` | 红色剑形门 | 红色剑形门框 | 中（策略3优先） |
| `red_door` | 红色门 | 红色普通门框 | 中（策略3优先） |

#### 组 B：特殊标志（互斥，不会与组 A 同时出现）

| 类型 ID | 名称 | 视觉特征 |
|---------|------|----------|
| `gold_diamond` | 金色菱形 | 金色菱形标记（小地图上） |

### 2.2 可扩展性设计

目标类型使用字符串枚举，新增类型只需：
1. 在 `TARGET_TYPES` 字典中添加定义
2. 准备对应的模板图片
3. 在选择策略中配置优先级

```python
# 可扩展的目标类型定义
TARGET_TYPES: dict[str, TargetTypeDef] = {
    "gold_door":       {"group": "door", "template": "path_target/gold_door.png"},
    "blue_door":       {"group": "door", "template": "path_target/blue_door.png"},
    "red_sword_door":  {"group": "door", "template": "path_target/red_sword_door.png"},
    "red_door":        {"group": "door", "template": "path_target/red_door.png"},
    "gold_diamond":    {"group": "special", "template": "path_target/gold_diamond.png"},
    # 新增类型在此添加...
}
```

---

## 3. 目标选择策略

### 3.1 策略类型

| 策略值 | 名称 | 选择逻辑 |
|--------|------|----------|
| `"priority"` | 优先级策略 | 按 target_priority 排序，同优先级选最近的 |
| `"nearest"` | 最近距离策略 | 始终选择距离最近的目标 |
| `"reverse_priority"` | 反向优先级策略 | 按反向 priority 排序，同优先级选最近的 |

### 3.2 默认优先级顺序

```
高 → gold_door, blue_door
中 → red_sword_door, red_door
低 → gold_diamond
```

### 3.3 参数格式

```jsonc
{
    "target_types": ["gold_door", "blue_door", "red_sword_door", "red_door", "gold_diamond"],
    "strategy": "priority",
    "target_priority": {
        "gold_door": 1,
        "blue_door": 1,
        "red_sword_door": 2,
        "red_door": 2,
        "gold_diamond": 3
    }
}
```

---

## 4. 到达判定

### 4.1 判定方式（多条件 OR）

| 条件 | 说明 | 触发阈值 |
|------|------|----------|
| **OCR 文字** | 目标旁出现特定文字 | 如"归来"、"进入"等 |
| **距离数字** | 距离标识小于阈值 | 默认 < 3 米 |

### 4.2 OCR 文字配置

```jsonc
{
    "arrival_text": ["归来", "进入", "交互"]
}
```

---

## 5. 寻路核心流程

### 5.1 主循环

```
                    ┌─────────────────┐
                    │   开始寻路       │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
            ┌──────►│ PathTargetReco   │◄──────┐
            │       │ (识别+选择目标)   │       │
            │       └────────┬─────────┘       │
            │                │                 │
            │     ┌──────────┼──────────┐      │
            │     ▼          ▼          ▼      │
            │  [无目标]  [已到达]  [有目标]     │
            │     │          │          │      │
            │     ▼          ▼          ▼      │
            │  返回失败   返回成功   AutoPath    │
            │                       Action      │
            │                       (移动+视角)  │
            └───────────────────────────────────┘
```

### 5.2 单次循环步骤

1. **识别阶段** (`PathTargetReco`)
   - 截图识别所有可见目标类型
   - 提取每个目标的屏幕坐标和距离数字
   - 执行选择策略，选出最优目标
   - 判断是否到达（OCR 文字 / 距离阈值）

2. **移动阶段** (`AutoPathAction`)
   - 计算目标相对于屏幕中心的偏移量
   - 若偏移过大 → 滑动视角使目标居中
   - 计算移动方向 → 滑动摇杆朝该方向移动
   - 检测障碍物（卡住、战斗、弹窗）

---

## 6. 组件详细设计

### 6.1 PathTargetReco（目标识别器）

**输入参数** (`custom_recognition_param`)：

```jsonc
{
    "target_types": ["gold_door", "blue_door", "..."],
    "strategy": "priority",
    "target_priority": { "gold_door": 1, ... },
    "arrival_text": ["归来", "进入"],
    "arrival_distance": 3
}
```

**输出结果** (`AnalyzeResult`)：

```python
# 未找到任何目标
AnalyzeResult(box=None, detail={"status": "no_target"})

# 找到目标但未到达
AnalyzeResult(
    box=(x, y, w, h),           # 最优目标的屏幕区域
    detail={
        "status": "navigating",
        "target_type": "gold_door",      # 目标类型
        "target_center": (cx, cy),       # 目标中心坐标
        "distance": 21.5,                # 距离（米）
        "direction": "right",            # 相对方向
        "offset_x": 320,                 # 相对屏幕中心的 X 偏移
        "offset_y": -180,                # 相对屏幕中心的 Y 偏移
    }
)

# 已到达目标
AnalyzeResult(
    box=(x, y, w, h),
    detail={
        "status": "arrived",
        "target_type": "red_door",
        "arrival_reason": "ocr_text",     # "ocr_text" 或 "distance"
        "detected_text": "归来"
    }
)
```

**识别逻辑**：

1. 对每种 `target_type` 执行模板匹配（或颜色匹配）
2. 对每个命中的目标，提取周围区域的距离数字（OCR）
3. 对每个命中的目标，检查周围是否有 `arrival_text`（OCR）
4. 执行选择策略，选出最优目标
5. 构建返回结果

### 6.2 AutoPathAction（寻路动作器）

**输入参数** (`custom_action_param`)：

```jsonc
{
    "move_duration": 500,
    "view_adjust_threshold": 100,
    "stuck_detection_frames": 30,
    "stuck_retry_count": 3
}
```

**执行逻辑**：

```python
def run(context, argv):
    # 1. 从 reco_detail 获取目标信息
    detail = argv.reco_detail
    if detail.get("status") == "arrived":
        return True  # 已到达，无需移动

    # 2. 视角调整：让目标居中
    offset_x = detail["offset_x"]
    offset_y = detail["offset_y"]
    if abs(offset_x) > view_adjust_threshold or abs(offset_y) > view_adjust_threshold:
        _adjust_view(context, offset_x, offset_y)

    # 3. 移动控制
    direction = _calculate_direction(detail)
    _move_toward(context, direction, move_duration)

    return True
```

**障碍物处理**：

| 障碍物 | 检测方法 | 处理方式 |
|--------|----------|----------|
| **卡住** | 连续 N 帧位置不变 | 微调方向后继续 |
| **战斗** | 识别战斗 UI | 等待战斗结束 |
| **弹窗** | 识别弹窗特征 | 关闭弹窗后继续 |
| **目标丢失** | 连续 N 帧无目标 | 原地旋转搜索 |

---

## 7. Pipeline 集成示例

### 7.1 基本 Pipeline 节点

```jsonc
{
    "AutoNavigate": {
        "recognition": { "type": "Custom", "param": {
            "custom_recognition": "PathTargetReco",
            "custom_recognition_param": {
                "target_types": ["gold_door", "blue_door", "red_sword_door", "red_door"],
                "strategy": "priority",
                "arrival_text": ["归来", "进入"],
                "arrival_distance": 3
            }
        }},
        "action": { "type": "Custom", "param": {
            "custom_action": "AutoPathAction",
            "custom_action_param": {
                "move_duration": 500,
                "view_adjust_threshold": 100
            }
        }},
        "next": ["TaskComplete"],
        "exceeded_next": ["NavigationFailed"]
    }
}
```

### 7.2 带重试的完整流程

```jsonc
{
    "StartNavigation": {
        "recognition": "DirectHit",
        "action": { "type": "Custom", "param": {
            "custom_action": "NodeOverride",
            "custom_action_param": { "node_name": "AutoNavigate" }
        }}
    },
    "AutoNavigate": {
        "recognition": { "type": "Custom", "param": {
            "custom_recognition": "PathTargetReco",
            "custom_recognition_param": { ... }
        }},
        "action": { "type": "Custom", "param": {
            "custom_action": "AutoPathAction"
        }},
        "next": ["TaskComplete"],
        "exceeded_next": ["RetryNav"],
        "times": 60,
        "timeout": 60000
    },
    "RetryNav": {
        "recognition": "DirectHit",
        "action": { "type": "Custom", "param": {
            "custom_action": "DisableNode",
            "custom_action_param": { "node_name": "AutoNavigate" }
        }},
        "next": ["StartNavigation"]
    },
    "TaskComplete": {
        "recognition": "DirectHit",
        "action": "DoNothing"
    },
    "NavigationFailed": {
        "recognition": "DirectHit",
        "action": "DoNothing"
    }
}
```

---

## 8. 平台适配

### 8.1 ADB 实现（当前）

| 操作 | 实现方式 |
|------|----------|
| 移动 | `Swipe` 从摇杆中心向方向向量滑动 |
| 视角 | `Swipe` 从屏幕中心向反方向滑动 |
| 截图 | Controller 内置 screencap |

### 8.2 Win32 预留（未来）

| 操作 | 预留接口 |
|------|----------|
| 移动 | 按下方向键（WASD 或方向键） |
| 视角 | 鼠标移动 |

通过 `PlatformFactory.detect_platform()` 自动选择实现。

---

## 9. 资源文件需求

### 9.1 模板图片

```
assets/resource/base/image/path_target/
├── gold_door.png         # 金色门模板
├── blue_door.png         # 蓝色门模板
├── red_sword_door.png    # 红色剑形门模板
├── red_door.png          # 红色门模板
└── gold_diamond.png      # 金色菱形模板
```

### 9.2 图片规格

- 分辨率基准：720p (1280x720)
- 格式：PNG（支持透明通道）
- 尺寸：根据实际目标大小裁剪，保留适当边距

---

## 10. 后续扩展考虑

1. **新目标类型**：在 `TARGET_TYPES` 字典添加即可
2. **新选择策略**：扩展 `_select_target()` 方法
3. **新到达条件**：扩展 `_check_arrival()` 方法
4. **新平台支持**：在 Action 中添加平台分支
5. **路径规划**：可集成 A* 或导航网格（如游戏提供 API）
