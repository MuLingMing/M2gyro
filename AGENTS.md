# M2gyro AI Agent 编码指南

欢迎参与 M2gyro 的开发！本指南旨在帮助 AI Agent 快速理解项目结构及编码规范，以提供更高质量的代码建议。

## 项目概览

M2gyro 是基于 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 开发的游戏自动化工具。

- **主体流程**：用户可以选择若干 Task 来执行自动化任务，位于 `assets/tasks` 目录。而 Task 会调用 Pipeline 中定义的 Node 来执行。Pipeline 是基于 JSON 的低代码实现，位于 `assets/resource/pipeline`。
- **复杂逻辑**：对于不便进行低代码实现的复杂的识别或操作逻辑，可通过 Python 编写的 `agent/custom` 来扩展实现。
- **配置入口**：`assets/interface.json` 定义了任务列表、控制器及 Agent 启动项。

## 关键文件

- [`assets/resource/pipeline/`](assets/resource/pipeline/): 所有的 Pipeline 任务逻辑。
- [`assets/resource/image/`](assets/resource/image/): 识别所需的图片资源（基准分辨率 720p）。
- [`agent/custom/`](agent/custom/): 自定义 Python Action/Recognition 源码。
- [`agent/OperationRecording/`](agent/OperationRecording/): 操作录制与回放模块。
- [`deps/tools/custom_act/`](deps/tools/custom_act/): Custom Action 的 JSON Schema 定义。
- [`deps/tools/custom_reco/`](deps/tools/custom_reco/): Custom Recognition 的 JSON Schema 定义。

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

- **协议合规性**：所有 Pipeline JSON 字段必须严格遵循 MaaFramework Pipeline 协议规范（见下方相关文档链接）。在新增或修改节点时，务必核对字段名称、类型及取值范围。
- **状态驱动**：遵循“识别 -> 操作 -> 识别”的循环。严禁盲目使用 `pre_delay` 或 `post_delay`。
- **高命中率**：尽可能扩充 `next` 列表，确保在第一轮截图（一次心跳）内命中目标节点。
- **原子化操作**：每一步点击或交互都应基于明确的识别结果，不要假设点击后的状态。
- **分辨率基准**：所有坐标和图片必须以 **720p (1280x720)** 为基准。

### 2. Python 注释规范

所有 Python 文件（特别是 Custom Action/Recognition 和 OperationRecording 模块）必须使用统一的注释风格：

- **文件级说明**：在文件顶部添加功能概述，列出主要功能点。
- **类级说明**：
  - 功能说明（分点列出）。
  - 参数格式示例（JSON 格式）。
  - 字段说明（每个参数的用途）。
- **方法级说明**：
  - 参数（类型和用途）。
  - 返回值（类型和用途）。
  - 执行流程（分点说明步骤）。
- **OperationRecordAction 特别要求**：类文档中需要包含完整的支持动作列表，包括每个动作的参数说明。

### 3. Python Custom Action/Recognition 规范

- **职责分离**：Python 模块仅用于处理 Pipeline 难以实现的复杂图像算法或特殊交互逻辑。
- **流程控制**：禁止在 Python 中编写大规模的业务流程，流程控制应交由 Pipeline JSON 负责。
- **注册机制**：新的自定义动作/识别需在 `custom.json` 中注册，具体实现参考 `agent/custom/` 目录下的示例。
- **类型提示**：所有函数和方法必须添加类型注解，确保代码可维护性。
- **停止响应**：执行过程中需检查 `context.tasker.stopping`，收到停止通知时及时返回。

### 4. MaaFramework 接口使用规范

- **文档优先**：使用 MaaFramework 接口前，必须先阅读相关文档和 MAA 库的源码，了解接口的正确用法和参数要求。
- **工具辅助**：优先使用 `maafw-doc-expert` 和 `maafw-fullstack-guide` 等 Skill 工具获取官方文档内容。
- **避免假设**：不要假设 Controller 或 Context 类的属性存在，应通过 `getattr()` 安全访问或查阅源码确认。
- **版本兼容**：注意不同 MaaFramework 版本的接口变化，确保代码与当前项目使用的版本兼容。

### 5. OperationRecording 模块规范

- **动作定义**：新动作应继承 `ActionBase` 基类，使用 `@register_action` 装饰器注册。
- **平台实现**：新动作需在 `platforms/desktop/` 和 `platforms/adb/` 中分别实现。
- **平台检测**：通过 `Controller.name` 和 `Controller.config` 属性检测平台类型（adb/desktop），使用 `getattr()` 安全访问动态属性。
- **时间线模式**：复杂动作序列应使用时间线模式，支持并行动作叠加。
- **模式识别**：普通模式和时间线模式的区分依据是 `operations` 列表中是否有 `duration` 或 `overlays` 字段（在顶层或 params 中）。
- **统一参数格式**：时间线模式中 `duration` 和 `overlays` 统一放在 `params` 中，顶层仅保留 `action` 和 `params`。
- **等待动作**：wait 动作支持两种方式：
  - `duration`：等待指定时长（默认 1.0 秒）
  - `until`：等待到目标时间点（仅限时间线模式，相对于时间线开始）
- **停止响应**：执行过程中需检查 `context.tasker.stopping`，收到停止通知时调用 `release_all()` 释放全部按键。
- **按键跟踪**：Desktop 平台需维护 `_active_keys` 集合跟踪已按下未释放的按键，ADB 平台维护 `_active_contacts` 字典。
- **类型注解**：所有函数和方法必须添加类型注解。
- **清理调试代码**：移除非必要的 `print` 语句和未使用变量。
- **Schema 同步**：OperationRecordAction 的 JSON Schema 需要同步更新到 `deps/tools/custom_act/OperationRecordAction.schema.json` 和 `deps/tools/custom.action.schema.json`。
- **平台命名规范**：桌面平台使用 `desktop` 而不是 `win32`，因为 `.gitignore` 中会忽略 `win32/` 目录。

### 6. 资源维护与任务新增

- **接口定义合规性**：`assets/interface.json` 必须符合 MaaFramework 项目接口 V2（见下方相关文档链接）规范。
- **配置同步**：`assets/interface.json` 的修改需要手动从 `install` 目录同步回源码（如果是通过工具修改）。

### 7. 代码格式化规范

- **Prettier 约束**：所有 JSON、YAML 文件必须遵循 `.prettierrc` 的配置。
- **关键规则**：

  - 缩进宽度以 `.prettierrc` 为唯一准则，通常是 4 个空格。
  - 数组格式受 `prettier-plugin-multiline-arrays` 插件影响，数组元素必须换行排列（阈值为 1）。
  - 提交前请务必执行格式化，确保代码风格统一。

## 审查重点

在审查代码（Review）时，请重点关注以下事项：

- **协议字段校验**：检查 Pipeline 和 Interface JSON 中的字段是否合法，是否存在拼写错误或使用了协议不支持的属性。参考相关协议文档。
- **禁止硬延迟**：检查是否出现了不必要的 `pre_delay`, `post_delay`, `timeout`。应优先考虑通过增加中间识别节点来优化流程。
- **截图效率**：检查 `next` 列表是否足够完善。理想情况下，应能覆盖当前操作后所有可能的预期画面，实现“一次心跳，立即命中”。
- **坐标合法性**：所有新定义的 `roi` 或 `target` 坐标必须基于 **1280x720** 分辨率。
- **代码格式化**：确保代码符合 `.prettierrc` 规范，特别是 JSON 中的缩进格式。
- **逻辑边界**：检查 Pipeline 是否处理了异常情况（如弹窗阻断）。每一步点击后都应有相应的识别验证。
- **Python 职责界限**：审查 Python 模块中的代码是否包含本应由 Pipeline 处理的业务逻辑。确保 Python 仅作为“工具”被 Pipeline 调用。
- **配置文件同步**：若修改了任务列表，务必确认 `assets/interface.json` 已正确更新。

## 相关文档链接

建议调取以下文档（通过读取文件或使用工具访问网页）以辅助理解和开发：

- [MaaFramework Pipeline 协议规范](https://github.com/MaaXYZ/MaaFramework/raw/refs/heads/main/docs/en_us/3.1-PipelineProtocol.md)
- [MaaFramework 项目接口 V2](https://github.com/MaaXYZ/MaaFramework/raw/refs/heads/main/docs/en_us/3.3-ProjectInterfaceV2.md)
