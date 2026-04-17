# Mask-Based PSD Export 设计文档

## 1. 背景与目标

当前流程是：抠图阶段输出 RGBA（透明通道）结果图，PSD 导出直接将该 RGBA 作为图层像素写入。这种方式可用，但后期编辑时不便：用户无法直接在 Photoshop 中编辑图层蒙版。

本次目标：

1. 将 PSD 导出模式改为 `原图图层 + 图层蒙版(mask)`。
2. 抠图阶段同时输出两类文件：
   - `matte.png`（RGBA，继续用于应用内预览）
   - `mask.png`（黑白灰度，供 PSD 图层蒙版）
3. 完全替换旧的 PSD RGBA 导出路径（不做 UI 开关）。

非目标：

1. 不重做抠图页 UI 交互（仍显示 RGBA 预览）。
2. 不新增导出模式选项。
3. 不改变素材扫描/选择流程。

## 2. 现状问题

1. PSD 内透明信息“烘焙”在像素层 alpha 里，不是可编辑蒙版。
2. 无独立 mask 文件落盘，无法在流程外复用蒙版。
3. 旧缓存结构仅追踪 `matte_path`，无法支撑“原图+mask”导出链路。

## 3. 方案概述（已确认）

采用“抠图双产物 + PSD 蒙版导出”的单一路径：

1. 抠图阶段：同一次推理产出 `matte_path` 与 `mask_path`。
2. 预览阶段：继续读取 `matte_path`（UI 不变）。
3. PSD 导出阶段：读取“原始素材图”与 `mask_path`，构建 `原图图层 + Layer Mask`。
4. 图层默认可见性：`visible = False`（眼睛关闭），保持当前工作流。

## 4. 详细设计

### 4.1 数据模型变更

`MatteRecord` 增加字段：

- `mask_path: str`

新结构：

- `source_id`
- `source_mtime`
- `matte_path`
- `mask_path`
- `is_active`

### 4.2 抠图引擎输出

`MattingEngine` 新增双输出能力：

- 输入：`input_path`
- 输出：
  - RGBA 图：`*_matte.png`
  - 灰度蒙版：`*_mask.png`（8-bit, 白=保留，黑=隐藏）

实现要求：

1. mask 与原图尺寸完全一致。
2. `matte` 的 alpha 与 `mask` 来自同一预测结果，避免漂移。
3. stub 模式下也产出 `mask`（全白）。

### 4.3 Worker 与状态流

`MattingWorker`：

1. 每个素材处理成功后回传双路径（至少回传可组装 `MatteRecord` 的数据）。
2. 组装 `MatteRecord` 时必须包含 `mask_path`。

缓存命中条件升级：

1. `source_id` 匹配
2. `source_mtime` 匹配
3. `is_active == true`
4. `matte_path` 与 `mask_path` 都存在

任一不满足即重算。

### 4.4 PSD 导出逻辑

导出时每个素材按以下方式写图层：

1. 图层像素：原始素材图（非 RGBA 抠图结果）。
2. 图层蒙版：`mask_path`。
3. 图层位置：画布居中（延续现有规则）。
4. 图层默认：`visible=False`。

失败策略：

- 任一 active 素材缺失 `mask_path` 或 mask 文件不可读，导出直接失败并给出可定位报错（包含素材名/路径）。

### 4.5 向后兼容与迁移

`state_manager.load_state` 兼容旧 JSON：

1. 旧记录无 `mask_path` 时可成功反序列化（例如给默认空串）。
2. 运行时缓存判断会把这类记录视为不可复用并自动重算。

无需离线迁移脚本。

## 5. 错误处理策略

1. 推理失败：标记素材失败，允许重试。
2. `matte` 成功但 `mask` 写入失败：按失败处理，不写 `MatteRecord`。
3. 导出阶段蒙版缺失/损坏：终止导出并显示明确错误。
4. 导出后回读校验：
   - 图层可见性应全部为 false。
   - 图层应存在有效蒙版（新增校验）。

## 6. 测试计划

### 6.1 单元测试

1. `core/birefnet.py`
   - 双输出文件都生成。
   - mask 为灰度图，尺寸正确。
2. `core/state_manager.py`
   - 旧 JSON（无 `mask_path`）可读。
3. `core/matte_cache.py`
   - 仅当 `matte_path`、`mask_path` 同时存在时命中。
4. `core/psd_export.py`
   - 产出 PSD 图层默认隐藏。
   - 每层蒙版存在。
   - 缺失蒙版时报错。

### 6.2 流程测试

1. `ui/workers/matting_worker.py`
   - 成功流程生成双路径并进入 `matte_map`。
2. `ui/main_window.py`
   - 旧状态恢复后会触发重算，而非错误中断。

### 6.3 人工验收

使用 Photoshop/Photopea 检查：

1. 每个图层都有可编辑蒙版。
2. 图层眼睛默认关闭。
3. 编辑蒙版（涂抹/羽化）可即时改变显示。

## 7. 风险与应对

1. 风险：pytoshop 在蒙版结构上的兼容性差异。
   - 应对：增加导出后结构校验与多查看器抽检。
2. 风险：文件数量翻倍导致临时目录增大。
   - 应对：沿用现有退出清理策略。
3. 风险：旧项目状态首次进入会触发重算，耗时增加。
   - 应对：在日志/提示中说明“旧缓存升级中”。

## 8. 分支建议

建议新开分支开发：

- `codex/mask-based-psd-export`

原因：本改动跨越模型输出、缓存策略、导出结构与测试，属于中等范围功能升级，适合隔离开发。

## 9. 验收标准

1. PSD 不再使用 RGBA 抠图图层作为最终像素来源。
2. PSD 中每层均为“原图 + 可编辑蒙版”。
3. 导出默认隐藏图层行为保持不变。
4. 旧状态不崩溃，可自动重算并完成导出。
5. 测试通过，且新增测试覆盖核心变更点。
