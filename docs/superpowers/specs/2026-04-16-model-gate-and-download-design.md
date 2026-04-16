# Folder Poster 模型门禁与下载页流程设计（参考 birefnet-gui 同款）

## 1. 背景与目标

当前项目在抠像任务启动后才懒加载模型，若模型不存在/不可用，失败会在逐条素材处理中暴露为行级失败，缺少“启动即检查 + 下载入口 + 硬拦截”流程。

本设计目标是按参考项目 `/Users/liujiahao/OthDev/birefnet-gui` 的模式改造为：

1. 应用启动即检查模型是否可用。
2. 模型缺失时强制进入模型下载页，主流程硬拦截。
3. 下载成功后无需重启，立即解锁主流程。
4. 推理仅使用本地模型目录加载，不允许运行时隐式在线拉模。

本期范围按用户确认：

- 门禁策略：硬拦截。
- 模型策略：单模型固定，仅支持 `ZhengPeng7/BiRefNet`。
- 参考实现策略：流程对齐参考项目，不做超范围扩展。

## 2. 现状问题

当前仓库核心链路如下：

- `ui/main_window.py` 在 `_on_materials_next()` 中直接启动 `MattingWorker`。
- `ui/workers/matting_worker.py` 在 `run()` 中创建 `MattingEngine`。
- `core/birefnet.py` 在 `predict_matte()` 首次调用时 `_load_model()`。
- `_load_model()` 直接 `AutoModelForImageSegmentation.from_pretrained(MODEL_ID, trust_remote_code=True)`，未指定本地目录与 `local_files_only=True`。

导致的问题：

1. 模型可用性检查时机过晚（任务已开始后才发现）。
2. 模型缺失与普通素材失败混在一起，用户无法明确下一步。
3. 运行时可能触发网络拉模，行为不可控。

## 3. 参考项目对齐点

参考项目关键模式：

1. 启动后检查 `has_any_model()`，无模型时切换到模型管理页并禁用开始处理。
2. 下载在独立 UI 中完成，带进度与失败重试。
3. 推理从本地模型目录加载，并使用 `local_files_only=True`。

本项目将保持同一用户心智，但映射到现有页面结构（Home/Materials/Matting/Export）。

## 4. 目标架构

### 4.1 新增模块：`core/model_manager.py`

职责：

1. 固定模型元信息（单模型）：
   - `repo_id = "ZhengPeng7/BiRefNet"`
   - `local_dir = ~/.folder-poster/models/birefnet`
2. 模型可用性检查：`is_installed()`
   - 以关键文件存在性为准（至少 `config.json`）
3. 下载模型：`download_model(progress_cb=None)`
   - 底层调用 `huggingface_hub.snapshot_download`
   - `resume_download=True`
   - 下载到固定本地目录
4. 提供推理层统一取路径接口：`get_model_dir()`

说明：

- 本期不支持多模型切换，不引入模型注册表 UI。
- 若后续扩展多模型，可在本模块演进，不影响上层页面。

### 4.2 调整模块：`core/birefnet.py`

改造点：

1. `_load_model()` 改为从 `ModelManager.get_model_dir()` 读取本地目录。
2. `from_pretrained()` 增加 `local_files_only=True`。
3. 模型目录不存在或关键文件缺失时，抛出明确可识别错误（如 `ModelNotInstalledError` 或带稳定前缀文案）。

边界：

- `core/birefnet.py` 只负责推理，不负责下载策略。
- 网络相关逻辑仅存在于 `ModelManager.download_model()`。

### 4.3 新增页面：`ui/pages/model_download_page.py`

页面职责：

1. 明确提示“未检测到模型，需要先下载”。
2. 提供下载按钮。
3. 展示进度条与阶段文本。
4. 下载失败时显示错误并提供重试。
5. 下载成功后发出 `model_ready` 信号。

交互约束：

- 在模型缺失状态下，该页为唯一主页面。
- 不提供跳过入口。

### 4.4 调整 `ui/main_window.py`

新增启动门禁流程：

1. 初始化 UI 后立即执行模型检查。
2. 若缺失：
   - 显示 `ModelDownloadPage`
   - 屏蔽进入 `HomePage -> Materials -> Matting -> Export` 的路径
3. 若存在：
   - 正常显示 `HomePage`
4. 下载页收到 `model_ready` 后：
   - 重新检查模型
   - 通过后切换回 `HomePage`

### 4.5 抠像页职责回归（与参考流程对齐）

在门禁生效后，`MattingPage` 与 `MattingWorker` 的职责边界需明确回归：

1. 抠像页只处理任务可视化、进度、失败重试与返回逻辑。
2. 抠像链路默认前置条件“模型已可用”，不再承载“缺模型引导下载”的分支 UI。
3. 若运行期出现模型损坏等异常，按统一错误出口回到下载页处理，不在抠像页内新增下载控件或分叉流程。

目标是保持抠像交互简单稳定，避免模型安装流程与任务执行流程耦合。

## 5. 状态流转设计

定义应用层状态：

1. `CHECKING_MODEL`
2. `MODEL_REQUIRED`
3. `READY`

流转：

1. 启动：`CHECKING_MODEL`
2. 检查失败：`MODEL_REQUIRED`
3. 用户下载成功并复检通过：`READY`

约束：

- `MODEL_REQUIRED` 状态下不允许触发扫描/素材选择/抠像任务。
- `READY` 后恢复原有流程。

## 6. 异常处理

### 6.1 下载异常

1. 网络异常：提示“下载失败，请检查网络后重试”。
2. 权限异常（模型目录不可写）：提示目录路径并要求修复权限。
3. 下载中断：可重试，利用断点续传继续。

### 6.2 推理前/推理期异常

1. 推理前复检失败：阻止任务启动并返回下载页。
2. 推理期遇到模型损坏/缺失：
   - 弹出明确提示
   - 引导回下载页重装
   - 不把该类错误当作普通素材失败吞掉

## 7. 数据与目录规范

固定目录：

- `~/.folder-poster/models/birefnet`

安装判定：

- 当前版本以 `config.json` 存在作为安装完成判定。
- 若后续发现需要更严格校验，可增加必要权重文件检查。

## 8. 测试策略

### 8.1 新增测试

1. `tests/core/test_model_manager.py`
   - `is_installed()`：目录不存在 / 关键文件缺失 / 正常存在
   - `download_model()`：成功与异常分支（mock `snapshot_download`）
2. `tests/test_model_download_page.py`
   - 下载按钮状态
   - 进度更新
   - 失败重试信号
3. `tests/test_main_window_model_gate.py`
   - 启动缺模型时显示下载页
   - 下载成功后切回首页并解锁

### 8.2 现有测试调整

1. `tests/core/test_birefnet.py`
   - 验证从本地目录加载
   - 验证 `local_files_only=True`
2. 与 `MainWindow` 流程耦合的测试按新初始状态补齐门禁前置。
3. `tests/test_matting_page.py` 与 `tests/test_matting_worker.py` 增加回归覆盖：
   - 在“模型已通过门禁”的前置下，现有进度、失败标记、重试按钮逻辑保持不变
   - 不引入模型缺失态到抠像页状态机

执行策略：

- 统一使用项目虚拟环境：`./scripts/test.sh`（或 `source .venv/bin/activate && pytest`）

## 9. 验收标准

1. 无模型环境首次启动直接进入下载页。
2. 未下载前主流程不可用（硬拦截成立）。
3. 下载成功后无需重启即可进入主页继续操作。
4. 抠像推理阶段仅本地加载，不发生隐式在线拉模。
5. 模型损坏时给出明确引导并可回到下载页修复。

## 10. 非目标（本期不做）

1. 多模型列表与切换。
2. 下载源设置页（镜像/官方切换）。
3. 模型删除与空间管理。
4. 离线包预置模型安装器。

## 11. 实施顺序建议

1. 先落 `ModelManager` 与 `core/birefnet.py` 本地加载约束。
2. 再接入 `ModelDownloadPage` 与 `MainWindow` 启动门禁。
3. 最后补测试并回归现有抠像流程。
