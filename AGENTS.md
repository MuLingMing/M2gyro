# M2gyro AI Agent 编码指南

要求积极使用合适的规则、智能体和 Skill。

## 项目概览

M2gyro 是基于 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 开发的游戏自动化工具。

- **主体流程**：用户选择 Task 执行自动化任务（`assets/tasks`），Task 调用 Pipeline 中的 Node（`assets/resource/pipeline`）。
- **复杂逻辑**：Pipeline 难以实现的识别/操作逻辑，通过 Python `agent/custom` 扩展。
- **配置入口**：`assets/interface.json` 定义任务列表、控制器及 Agent 启动项。

## 关键文件

- [`assets/resource/pipeline/`](assets/resource/pipeline/): Pipeline 任务逻辑。
- [`assets/resource/image/`](assets/resource/image/): 识别图片资源（基准 720p）。
- [`assets/tasks/`](assets/tasks/): 任务定义文件。
- [`agent/custom/`](agent/custom/): 自定义 Python Action/Recognition 源码。
- [`agent/custom.json`](agent/custom.json): 自定义 Action/Recognition 注册配置。
- [`agent/OperationRecording/`](agent/OperationRecording/): 操作录制与回放模块（统一模块注册体系 + 平台家族继承）。
- [`deps/tools/custom_act/`](deps/tools/custom_act/) / [`deps/tools/custom_reco/`](deps/tools/custom_reco/): JSON Schema（IDE 悬停提示）。
- [`.trae/skills/`](.trae/skills/): Trae IDE Skill 配置（自动发现）。
- [`rules/`](rules/): 用户规则文件目录。

## 交互规范

遵循用户设置的以下规范（详见 [`rules/`](rules/) 目录）：

- 「需求分析与方案确认规范」- 需求分析、方案生成与用户确认流程
- 「任务清单规范」- 任务分解与状态跟踪（需先完成需求确认）
- 「分段输出规范」- 长内容输出策略
- 「开发八荣八耻」- 核心开发原则
- 「文件修改策略规则」- 文件修改策略规则
- 「错误处理规范」- 错误处理流程与重试机制

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

详见 [`agent/OperationRecording/`](agent/OperationRecording/) 目录。

**核心架构：**

- **统一模块注册**：`ModuleRegistry[T]` 泛型基类，`ActionRegistry`/`EffectRegistry`/`PlatformRegistry` 三种注册表完全对称。
- **平台家族继承**：`KeyboardPlatform`/`TouchPlatform` 家族基类提供默认实现，子类（`DesktopPlatform`/`AdbPlatform`）仅需提供映射表。

**关键流程：**

- **新增动作**：Action 类注册 → 平台家族基类添加默认方法 → `__init__.py` 导入 → Schema 更新
- **新增效果插件**：`@register_effect` + `builtin/__init__.py` 导入 + `default.json` 配置

**不再需要修改**：`timeline.py`、`executor.py`、`parser.py`

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
- **详细规范**：参考 [`json-schema-creator` Skill](.trae/skills/json-schema-creator/SKILL.md)。

### 7. Trae Skills 使用规范

- **自动发现**：Trae 扫描 `.trae/skills/*/SKILL.md` 的 YAML frontmatter 自动注册。
- **Frontmatter**：`---` 开头 YAML 块，含 `name`（唯一标识）和 `description`（英文单行触发条件）。
- **调用时机**：涉及 Skill 描述领域时主动调用。
- **现有 Skill**：`maaframework`、`maafw-doc-agent`、`maafw-project`、`maafw-cli`、`json-schema-creator`、`markdown-format`、`mcp`。

## 审查重点

### Pipeline 审查

- 协议字段校验，禁止硬延迟
- next 列表覆盖完整，坐标基于 720p
- 逻辑边界处理（弹窗阻断等）

### Python 审查

- 类型安全：可空类型守卫，正交状态设计
- 参数语义：穷举验证，追踪完整链路
- 空值守卫：统一使用 is None/is not None

### OperationRecording 审查

- 新动作是否正确注册到对应平台家族基类
- 效果插件是否完成三处同步（`@register_effect`、`__init__.py` 导入、`default.json` 配置）
- Schema 是否与代码实现一致

### 配置同步

- interface.json 与任务列表同步
- Schema 的 allOf 同步更新
- 效果插件三处同步

## 相关文档链接

- [MaaFramework Pipeline 协议规范](https://github.com/MaaXYZ/MaaFramework/raw/refs/heads/main/docs/en_us/3.1-PipelineProtocol.md)
- [MaaFramework 项目接口 V2](https://github.com/MaaXYZ/MaaFramework/raw/refs/heads/main/docs/en_us/3.3-ProjectInterfaceV2.md)
- [`json-schema-creator` Skill](.trae/skills/json-schema-creator/SKILL.md)
- [`maafw-doc-agent` Skill](.trae/skills/maafw-doc-agent/SKILL.md)
- [`maafw-project` Skill](.trae/skills/maafw-project/SKILL.md)
