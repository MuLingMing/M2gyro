# M2gyro AI Agent 编码指南

> 项目级规则，与用户级全局规则（`<user_rules>`）互补。冲突时项目规则优先。

## 项目概览

基于 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 的游戏自动化工具。

- **主体流程**：Task（`assets/tasks`）→ Pipeline Node（`assets/resource/pipeline`）。
- **复杂逻辑**：Python `agent/custom` 扩展。
- **配置入口**：`assets/interface.json`（任务列表、控制器、Agent 启动项）。

## 关键文件

- [`assets/resource/pipeline/`](assets/resource/pipeline/): Pipeline 任务逻辑。
- [`assets/resource/image/`](assets/resource/image/): 识别图片资源（基准 720p）。
- [`assets/tasks/`](assets/tasks/): 任务定义文件。
- [`agent/custom/`](agent/custom/): 自定义 Python Action/Recognition 源码。
- [`agent/custom.json`](agent/custom.json): 自定义 Action/Recognition 注册配置。
- [`agent/OperationRecording/`](agent/OperationRecording/): 操作录制与回放模块。
- [`deps/tools/custom_act/`](deps/tools/custom_act/) / [`deps/tools/custom_reco/`](deps/tools/custom_reco/): JSON Schema（IDE 悬停提示）。
- [`.trae/skills/`](.trae/skills/): Trae IDE Skill 配置。
- [`.trae/rules.bak/`](.trae/rules.bak/): 用户规则备份。

## 编码规范

### 1. Pipeline 低代码规范

- 严格遵循 [MaaFramework Pipeline 协议](https://github.com/MaaXYZ/MaaFramework/raw/refs/heads/main/docs/en_us/3.1-PipelineProtocol.md)。
- 遵循"识别 → 操作 → 识别"循环，严禁盲目使用 `pre_delay`/`post_delay`。
- 扩充 `next` 列表，确保一次心跳内命中目标节点；每一步基于明确识别结果。
- 所有坐标和图片以 **720p (1280x720)** 为基准。

> **审查**：协议字段校验；next 列表覆盖完整，坐标基于 720p；逻辑边界处理（弹窗阻断等）。

### 2. Python 开发规范

**注释**：文件级（功能概述）、类级（功能说明+参数示例）、方法级（参数/返回值/执行流程）、OperationRecordAction（完整动作列表及参数说明）。

**Custom Action/Recognition**：Python 仅处理 Pipeline 难以实现的复杂逻辑，流程控制交由 Pipeline JSON。新动作/识别需在 `custom.json` 注册。所有函数和方法必须添加类型注解。执行中检查 `context.tasker.stopping` 及时返回。

**类型安全**：
- 可空类型（`int | None`）算术操作前必须 `is not None` 守卫。
- 多状态维度保持正交关系。
- 新增参数时穷举所有类型组合验证行为。
- 新增配置参数时追踪完整使用链路（解析 → 存储 → 读取）。
- 功能不同的节点应有独立 Schema 定义，不复用通用定义。

**MaaFramework 接口**：使用前查阅文档和源码，优先使用 Skill 获取指导。不假设 Controller/Context 属性存在，通过 `getattr()` 安全访问。

> **审查**：类型安全（可空守卫、正交状态）；参数语义（穷举验证、追踪链路）；空值统一使用 `is None`/`is not None`。

### 3. OperationRecording 模块规范

**架构**：`ModuleRegistry[T]` 泛型基类，`ActionRegistry`/`EffectRegistry`/`PlatformRegistry` 对称。`KeyboardPlatform`/`TouchPlatform` 家族基类提供默认实现，子类仅需映射表。

**新增流程**：
- 动作：Action 类注册 → 平台家族基类添加默认方法 → `__init__.py` 导入 → Schema 更新。
- 效果插件：`@register_effect` + `builtin/__init__.py` 导入 + `default.json` 配置。

**不再需要修改**：`timeline.py`、`executor.py`、`parser.py`。

> **审查**：动作注册到对应平台家族基类；效果插件三处同步；Schema 与代码实现一致。

### 4. 资源维护与任务新增

- `assets/interface.json` 必须符合 [项目接口 V2 规范](https://github.com/MaaXYZ/MaaFramework/raw/refs/heads/main/docs/en_us/3.3-ProjectInterfaceV2.md)。
- 构建后 `install/` 中的配置副本需手动同步回 `assets/` 源码目录。

> **审查**：interface.json 与任务列表同步；Schema 的 `allOf` 同步更新。

### 5. 代码格式化规范

- JSON、YAML 遵循 `.prettierrc`；数组元素必须换行（`prettier-plugin-multiline-arrays`，阈值 1）。
- 提交前执行格式化。

### 6. JSON Schema 规范

- 主 Schema 定义公共属性 + `allOf` 合并子 Schema；子 Schema 用 `if/then` 条件验证。
- `$ref` 的 `description` 放在 `definitions` 中的目标定义里；`if/then` 中 `$ref` + `description` 可同级使用。
- 新增/修改时更新子 Schema 和主 Schema 的 `allOf` 引用。详见 [`json-schema-creator` Skill](.trae/skills/json-schema-creator/SKILL.md)。

### 7. Trae Skills 使用规范

- Trae 扫描 `.trae/skills/*/SKILL.md` 的 YAML frontmatter 自动注册。
- 涉及 Skill 描述领域时主动调用；可用 Skill 列表通过 `Skill` 工具动态获取。

## 相关文档

- [MaaFramework Pipeline 协议规范](https://github.com/MaaXYZ/MaaFramework/raw/refs/heads/main/docs/en_us/3.1-PipelineProtocol.md)
- [MaaFramework 项目接口 V2](https://github.com/MaaXYZ/MaaFramework/raw/refs/heads/main/docs/en_us/3.3-ProjectInterfaceV2.md)
- [`json-schema-creator` Skill](.trae/skills/json-schema-creator/SKILL.md)
- [`maafw-doc-agent` Skill](.trae/skills/maafw-doc-agent/SKILL.md)
- [`maafw-project` Skill](.trae/skills/maafw-project/SKILL.md)
