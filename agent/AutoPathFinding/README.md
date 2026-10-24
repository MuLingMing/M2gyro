# AutoPathFinding 自动寻路模块（重构版）

## 1. 模块概述

根据游戏截图识别指定目标图标，结合 OCR 距离信息自动移动/转向到达目标点。

本版为完全重构：闭环控制从无状态回调的 ClassVar 全局态迁移到显式会话对象
（`NavigationController`），决策逻辑收敛为可单测的纯函数状态机。

## 2. 架构

```
Pipeline JSON（只做 启动会话 / 中断 / 分支 / 超时）
        │
┌───────┴────────┐  ┌────────────────┐
│ PathFindingReco│  │PathFinderAction│      薄适配层（仅转发）
│ (识别回调)     │──▶│ (动作回调)     │      argv.node_name 区分会话
└───────┬────────┘  └────────┬───────┘
        │    NavigationSession（按 node_name 一份）
        ▼                    ▼
┌─────────────────────────────────────────┐
│           navigation 包（核心）          │
│  Perception  感知：模板匹配 + OCR 距离   │
│  Estimator   估计：锁定/追踪/方位/卡住   │
│  Policy      决策：纯函数状态机          │
│  Executor    执行：唯一平台调用出口      │
└───────────────────┬─────────────────────┘
                    ▼
          PlatformFactory (OperationRecording)
          move / turn / dodge / interact / release_all
```

### 2.1 文件

| 文件 | 职责 |
| --- | --- |
| `navigation/geometry.py` | 纯函数：8 向分箱、偏差角、转向分级/坐标计算 |
| `navigation/params.py` | `NavigationParams` dataclass（参数单一事实来源） |
| `navigation/perception.py` | `ScreenPerceiver`：模板匹配收集目标 + OCR 距离 |
| `navigation/estimator.py` | 锁定/IOU 追踪、`RotationAdjuster`(EMA)、`StuckDetector` |
| `navigation/policy.py` | `decide()` 纯函数状态机 |
| `navigation/executor.py` | `NavExecutor`：命令→平台操作（时长全秒） |
| `navigation/controller.py` | `NavigationController` 会话注册表 + 帧编排 |
| `recognition/path_finding_reco.py` | 薄壳：analyze→session.perceive |
| `action/path_finder_action.py` | 薄壳：run→session.act |
| `action/navigation_session_action.py` | `PathFindingInit` / `PathFindingRelease` |
| `selector/` | 目标选择器插件（priority / nearest / composite） |

### 2.2 状态机

```
SEARCH ──有目标──▶ TRACK ⇄ APPROACH ──距离≤arrival──▶ ARRIVE
  ▲                 │
  └── 锁定超时 ──────┘
 任何相位：连续无进展→RECOVER（dodge 脱困）
          卡住超过 stuck_timeout_ms → FAIL（识别不命中，pipeline 走兜底分支）
```

## 3. Pipeline 用法

```json
{
	"NavInit": {
		"action": "PathFindingInit",
		"custom_action_param": {
			"expected_templates": [
				"quest_icon"
			],
			"selector_type": "priority",
			"distance_pattern": "(\\d+)米"
		},
		"next": [
			"NavLoop"
		]
	},
	"NavLoop": {
		"recognition": "PathFindingReco",
		"action": "PathFinderAction",
		"timeout": 120000,
		"next": [
			"NavArrived",
			"NavLoop"
		]
	},
	"NavArrived": {
		"action": "PathFindingRelease",
		"next": []
	}
}
```

- `PathFindingInit` 的参数与 `PathFindingReco` 完全一致（同一 `NavigationParams`）。
- FAIL 相位时识别不命中（hit=False），可通过 pipeline 的超时/interrupt 机制走兜底，
  兜底分支务必执行 `PathFindingRelease`（会松开所有按键）。
- 不同导航节点使用不同 node_name，会话相互独立。

## 4. 相对旧版的行为变化

| 变化 | 旧版 | 新版 |
| --- | --- | --- |
| 会话状态 | ClassVar 全局，多节点共享 | 按 node_name 显式会话，Init/Release 管理 |
| 卡住超时 | `stuck_timeout_ms` 只解析不生效 | 真实生效：超时 → FAIL 相位 |
| 转向分级 | 帧间角度差，LARGE_TURN 几乎不触发 | 按目标偏离中心偏差角分级 |
| 自适应转速 | EMA 只在测试中调用，恒 1.0 | 真实接入转向距离计算 |
| 方向分箱 | 4 向 | 8 向（含斜向），带滞回 |
| 卡住处理 | 仅 dodge | 独立 RECOVER 相位 + 超时 FAIL |
| OCR ROI | x/y 裁剪但宽高不裁 | 宽高同步裁剪到屏幕内 |
| phase 赋值 | 两处赋值互相覆盖 | policy 单一来源 |

## 5. 小地图自状态（第一档，默认关闭）

`navigation/minimap.py`：`MinimapTracker.update(image) → MinimapObservation(heading_deg/heading_valid/speed_px_s/speed_valid)`。

- 朝向：圆形掩膜 + HSV 清洗（剔白 UI/彩色图标/暗区）→ 中心窗口最大亮轮廓 → 离质心最远点为箭头尖端 → atan2（约定正上=90°，与 geometry 一致）→ 环绕感知 EMA。
- 速度：清洗后小地图帧间相位相关（`cv2.phaseCorrelate`）求位移 → EMA。玩家箭头恒居中，不能用箭头位置差分。
- 接线：`enable_minimap=True` + 实机标定 `minimap_roi` 后生效。生效后——
  - SEARCH 变为有界环视：固定步长扫描，累计转角 ≥ `search_scan_deg` 仍未发现 → FAIL（不再无限盲走）；
  - 转向变为 P 控制：误差=目标角-朝向，死区 `steer_deadband_deg`，行进/原地双限幅（MaaEnd-2 经验值）；
  - 卡住检测增加速度判据：`speed ≤ speed_stuck_px_s` 视为原地，且优先于中心/距离判据。
  - 无朝向反馈时全部回退旧开环逻辑，行为不变。

启用步骤：跑一次委托截 3~5 帧带小地图的截图 → 定 `minimap_roi` 与清洗阈值（默认值为 MaaEnd-2 经验起点）→ 节点 param 中 `enable_minimap: true`。

## 6. 测试

```bash
.venv/Scripts/python -m pytest agent/AutoPathFinding/tests -q
```

覆盖：geometry 纯函数（分箱/分级/偏差角）、policy 状态机全相位、
params 别名与单位换算、minimap 合成图像朝向（±5°）/速度/禁用回退、
有界 SEARCH 与 P 转向死区。
