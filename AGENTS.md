# M2gyro AI Agent 编码指南

要求要积极使用合适的规则、智能体和skill

## 项目概览

M2gyro 是基于 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 开发的游戏自动化工具。

- **主体流程**：用户选择 Task 执行自动化任务（`assets/tasks`），Task 调用 Pipeline 中的 Node（`assets/resource/pipeline`）。
- **复杂逻辑**：Pipeline 难以实现的识别/操作逻辑，通过 Python `agent/custom` 扩展。
- **配置入口**：`assets/interface.json` 定义任务列表、控制器及 Agent 启动项。

## 关键文件

- [`assets/resource/pipeline/`](assets/resource/pipeline/): Pipeline 任务逻辑。
- [`assets/resource/image/`](assets/resource/image/): 识别图片资源（基准 720p）。
- [`agent/custom/`](agent/custom/): 自定义 Python Action/Recognition 源码。
- [`agent/custom.json`](agent/custom.json): 自定义 Action/Recognition 注册配置。
- [`agent/OperationRecording/`](agent/OperationRecording/): 操作录制与回放模块（统一模块注册体系 + 平台家族继承）。
- [`deps/tools/custom_act/`](deps/tools/custom_act/) / [`deps/tools/custom_reco/`](deps/tools/custom_reco/): JSON Schema（IDE 悬停提示）。
- [`.trae/skills/`](.trae/skills/): Trae IDE Skill 配置（自动发现）。

## 交互规范

### 需求确认

提出需求时使用嵌套提问功能先确认完整的需求：

- **首次提问**：针对需求中的关键要素提问（范围、边界条件、优先级等）。
- **追问确认**：如果提问后仍有不确定的需求及情况则继续提问。
- **确认清单**：完成前汇总确认所有已知条件和未解决的问题。

### 任务分解

进行任务时创建嵌套的任务清单来完成任务，即细分为各组件分别完成：

- **顶级任务**：主要目标。
- **子任务**：分解为具体步骤。
- **状态跟踪**：使用 TodoWrite 工具跟踪进度，标记 in_progress / completed。

## 编码规范

### 1. Pipeline 低代码规范

- **协议合规性**：所有 Pipeline JSON 字段必须严格遵循 MaaFramework Pipeline 协议规范（见下方相关文档链接）。
- **状态驱动**：遵循"识别 → 操作 → 识别"循环。严禁盲目使用 `pre_delay` 或 `post_delay`。
- **高命中率**：扩充 `next` 列表，确保一次心跳内命中目标节点。
- **原子化操作**：每一步交互都基于明确的识别结果，不假设点击后的状态。
- **分辨率基准**：所有坐标和图片以 **720p (1280x720)** 为基准。

### 2. Python 开发规范

#### 2.1 注释规范

- **文件级**：顶部功能概述，列出主要功能点。
- **类级**：功能说明、参数格式示例（JSON）、字段说明。
- **方法级**：参数/返回值（类型和用途）、执行流程。
- **OperationRecordAction**：类文档需包含完整的支持动作列表及参数说明。

#### 2.2 Custom Action/Recognition 规范

- **职责分离**：Python 仅处理 Pipeline 难以实现的复杂逻辑，流程控制交由 Pipeline JSON。
- **注册机制**：新自定义动作/识别需在 `custom.json` 中注册。
- **类型提示**：所有函数和方法必须添加类型注解。
- **停止响应**：执行过程中检查 `context.tasker.stopping`，收到停止通知时及时返回。

#### 2.3 类型安全（经验教训）

- **可空类型守卫**：`int | None` 等可空类型在算术操作前必须 `is not None` 守卫，即使运行时逻辑上不会为 None。
- **正交状态设计**：多状态维度应保持正交关系。如 `is_exhausted` 仅检查控制"是否参与识别"的维度，不混合检查控制"是否执行任务"的维度。
- **参数语义验证**：新增或修改参数时，穷举所有类型组合验证行为（如 bool×bool、bool×int、int×bool、int×int）。
- **死代码检测**：新增配置参数时，追踪完整使用链路（解析 → 存储 → 读取），确认参数是否被实际消费。
- **Schema 独立定义**：功能不同的节点应有独立的 Schema 定义，而非复用通用定义。

#### 2.4 MaaFramework 接口使用

- **文档优先**：使用接口前先阅读文档和源码，了解正确用法。优先使用 `maafw-doc-agent` 等 Skill 获取指导。
- **避免假设**：不假设 Controller/Context 属性存在，通过 `getattr()` 安全访问或查阅源码确认。

### 3. OperationRecording 模块规范

#### 架构

- **统一模块注册**：`ModuleRegistry[T]` 泛型基类，`ActionRegistry`/`EffectRegistry`/`PlatformRegistry` 三种注册表完全对称。
- **平台家族继承**：`KeyboardPlatform`/`TouchPlatform` 家族基类提供默认实现，子类（`DesktopPlatform`/`AdbPlatform`）仅需提供映射表。

```
PlatformBase (抽象基类)
├── KeyboardPlatform (键盘家族) → DesktopPlatform
└── TouchPlatform (触控家族) → AdbPlatform
```

#### 动作定义

- **注册**：继承 `ActionBase`，使用 `@register_action("name")` 注册。
- **声明式调度**：通过 `timeline_meta` 声明时间线行为，无需修改 `timeline.py`/`executor.py`/`parser.py`。

```python
# 持续动作（如移动、蓄力攻击、下蹲）
timeline_meta = TimelineMeta(has_duration=True, release_method="move")

# 瞬时动作（如跳跃、闪避、转向）
timeline_meta = TimelineMeta(has_duration=False)
```

调度规则：

- `has_duration=True` + `duration > 0`：`start(params)` → 等待 → `release_action(release_method)`
- `has_duration=True` + `duration = 0`：仅 `start(params)`（按下不释放）
- `has_duration=False`：`execute(params)`（瞬时完成）

#### 平台层

- **统一释放**：`release_action(action_name)` 统一释放，未知动作返回 `False`。
- **状态跟踪**：KeyboardPlatform 维护 `_active_keys`（set），TouchPlatform 维护 `_active_contacts`（Dict[str, int]）。
- **平台检测**：`PlatformFactory.detect_platform()` 通过 `controller.name` 自动判断，默认回退 `"adb"`。
- **平台命名**：桌面平台用 `desktop`（`.gitignore` 忽略 `win32/`）。
- **空值守卫**：所有平台方法在访问 `self._controller` 前必须 `if self._controller is None: return False`。

#### 新增动作流程

- **类型 A（依赖平台）**：Action 类注册 → 平台家族基类添加默认方法 → `__init__.py` 导入 → Schema 更新
- **类型 B（不依赖平台）**：Action 类注册 → `__init__.py` 导入 → Schema 更新

**不再需要修改**：`timeline.py`、`executor.py`、`parser.py`

#### 效果插件系统

遵循开闭原则，新增效果无需修改核心代码。

- **插件基类**：`EffectBase`，需实现 `apply()` 接口，可选覆写 `pre_action()`/`post_action()`。
- **注册机制**：`@register_effect("name")` 装饰器自动注册到 `effect_registry`。
- **管理器**：`EffectManager` 统一调度，支持全局开关和单插件独立 `enabled` 控制。
- **配置驱动**：`default.json` 的 `effects.plugins` 节点定义各插件配置。

新增效果插件流程：

1. 创建效果类文件（`effects/builtin/my_effect.py`）
2. 使用 `@register_effect("my_effect")` 注册
3. 在 `effects/builtin/__init__.py` 中导入触发注册
4. 在 `default.json` 的 `effects.plugins` 中添加配置

**不再需要修改**：`timeline.py`、`executor.py`、`parser.py`

#### 时间线模式

- **自动检测**：`operations` 中任一项包含 `duration` 或 `overlays` 字段时自动启用。
- **统一参数格式**：`duration`/`overlays` 放 `params` 内，顶层仅保留 `action` 和 `params`。
- **等待动作**：支持 `duration`（等待时长）和 `until`（绝对时间点）。
- **停止响应**：检查 `context.tasker.stopping`，收到停止信号时调用 `release_all()` 释放全部按键/触点。
- **释放失败处理**：`release_action()` 返回 `False` 时，动作标记为 `CANCELLED` 并记录日志。

### 4. 资源维护与任务新增

- `assets/interface.json` 必须符合 MaaFramework 项目接口 V2 规范。
- 修改需手动从 `install` 目录同步回源码。

### 5. 代码格式化规范

- 所有 JSON、YAML 文件遵循 `.prettierrc` 配置。
- 缩进以 `.prettierrc` 为准，数组元素必须换行（`prettier-plugin-multiline-arrays`，阈值 1）。
- 提交前执行格式化。

### 6. JSON Schema 规范

- **架构模式**：主 Schema 定义公共属性 + `allOf` 合并子 Schema；子 Schema 用 `if/then` 条件验证。
- **`$ref` 忽略同级 `description`**：嵌套对象的 `description` 放在 `definitions` 中的目标定义里。
- **`if/then` 中可用 `$ref` + `description`**：`then` 块的属性级别可同级使用。
- **Schema 同步**：新增/修改时更新子 Schema 和主 Schema 的 `allOf` 引用。
- **详细规范**：参考 `json-schema-creator` Skill。

### 7. Trae Skills 使用规范

- **自动发现**：Trae 扫描 `.trae/skills/*/SKILL.md` 的 YAML frontmatter 自动注册。
- **Frontmatter**：`---` 开头 YAML 块，含 `name`（唯一标识）和 `description`（英文单行触发条件）。
- **调用时机**：涉及 Skill 描述领域时主动调用。
- **现有 Skill**：`maaframework`、`maafw-doc-agent`、`maafw-project`、`maafw-cli`、`json-schema-creator`、`markdown-format`、`mcp`。

## 审查重点

- **协议字段校验**：Pipeline/Interface JSON 字段是否合法，有无拼写错误。
- **禁止硬延迟**：优先增加识别节点，避免 `pre_delay`/`post_delay`/`timeout`。
- **截图效率**：`next` 列表覆盖所有预期画面，一次心跳命中。
- **坐标合法性**：`roi`/`target` 坐标基于 **1280x720**。
- **代码格式化**：JSON 符合 `.prettierrc`。
- **逻辑边界**：Pipeline 处理异常情况（弹窗阻断等），每步点击有识别验证。
- **Python 职责界限**：Python 不含 Pipeline 应处理的业务逻辑。
- **配置文件同步**：修改任务列表后确认 `assets/interface.json` 已更新。
- **Schema 一致性**：子 Schema 和主 Schema 的 `allOf` 同步更新；`description` 放在 `definitions` 内。
- **类型安全**：可空类型算术操作前 `is not None` 守卫；状态维度正交，不混合判断。
- **参数语义**：穷举类型组合验证行为；追踪新参数完整使用链路，排除死代码。
- **效果插件三处同步**：`@register_effect` + `builtin/__init__.py` 导入 + `default.json` 配置。
- **空值守卫一致性**：平台方法统一使用 `is None`/`is not None`，禁止 truthy 检查 `self._controller`。

## 相关文档链接

- [MaaFramework Pipeline 协议规范](https://github.com/MaaXYZ/MaaFramework/raw/refs/heads/main/docs/en_us/3.1-PipelineProtocol.md)
- [MaaFramework 项目接口 V2](https://github.com/MaaXYZ/MaaFramework/raw/refs/heads/main/docs/en_us/3.3-ProjectInterfaceV2.md)
- [`json-schema-creator` Skill](.trae/skills/json-schema-creator/SKILL.md)
