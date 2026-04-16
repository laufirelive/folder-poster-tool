# Folder Poster 模型门禁与下载页执行计划

**关联设计文档：** `docs/superpowers/specs/2026-04-16-model-gate-and-download-design.md`

**目标：**
1. 对齐参考项目流程：启动先检模、缺模强制下载、下载后解锁。
2. 推理只从本地模型目录加载（禁用隐式在线拉模）。
3. 抠像页职责回归：假定模型可用，不引入缺模分支 UI。
4. 以指定图片 `/Users/liujiahao/Documents/testimge/OIP-2190781769.jpg` 完成端到端实测。

---

## Task 1: ModelManager 落地（核心模型能力）
**涉及文件：**
- `core/model_manager.py`（新建）

**实施要点：**
1. 固定单模型配置：`repo_id=ZhengPeng7/BiRefNet`。
2. 固定本地目录：`~/.folder-poster/models/birefnet`。
3. 实现 `is_installed()`（最小判定：`config.json` 存在）。
4. 实现 `download_model()`，封装 `snapshot_download(..., resume_download=True)`。
5. 输出统一接口 `get_model_dir()` 供推理层调用。

**完成标志：**
- 不依赖 UI 即可独立判断模型存在与触发下载。

---

## Task 2: 推理层本地化加载约束
**涉及文件：**
- `core/birefnet.py`

**实施要点：**
1. `_load_model()` 改为通过 `ModelManager` 获取本地目录。
2. `from_pretrained()` 增加 `local_files_only=True`。
3. 模型缺失时报稳定可识别错误（供上层跳转下载页）。

**完成标志：**
- 抠像推理链路不会隐式联网拉模。

---

## Task 3: 下载页 UI 与后台下载线程
**涉及文件：**
- `ui/pages/model_download_page.py`（新建）
- `ui/pages/__init__.py`

**实施要点：**
1. 页面显示缺模提示、下载按钮、进度条、错误提示与重试。
2. 下载动作放入后台线程，发射进度/完成/失败信号。
3. 下载成功发 `model_ready` 信号给主窗口。

**完成标志：**
- 可在不阻塞 UI 的情况下完成模型下载并反馈状态。

---

## Task 4: MainWindow 启动门禁接入（硬拦截）
**涉及文件：**
- `ui/main_window.py`

**实施要点：**
1. 启动时执行模型检查。
2. 若缺模：只显示下载页，不允许进入主流程。
3. 下载完成后复检通过，切换回 `HomePage`。
4. 运行期若检测到模型损坏错误，统一回下载页，不在抠像页处理下载。

**完成标志：**
- 缺模场景下，用户无法绕过下载页进入抠像链路。

---

## Task 5: 测试补齐与回归
**涉及文件：**
- `tests/core/test_model_manager.py`（新建）
- `tests/test_model_download_page.py`（新建）
- `tests/test_main_window_model_gate.py`（新建）
- `tests/core/test_birefnet.py`（更新）
- `tests/test_matting_page.py` / `tests/test_matting_worker.py`（必要回归补充）

**实施要点：**
1. 核心逻辑以 mock 隔离网络下载。
2. 覆盖缺模启动、下载成功解锁、本地加载约束。
3. 验证抠像页行为未因门禁改造产生退化。

**执行命令：**
- `./scripts/test.sh`

---

## Task 6: 指定样本端到端实测
**输入样本：**
- `/Users/liujiahao/Documents/testimge/OIP-2190781769.jpg`

**执行步骤：**
1. 启动应用，若缺模则先在下载页完成模型下载。
2. 选择样本图片并进入抠像流程。
3. 完成抠像并确认结果可预览。
4. 导出/保存结果到：
   - `/Users/liujiahao/Documents/testimge/OIP-2190781769_matte.png`

**验收点：**
1. 全链路无模型缺失误报。
2. 输出文件存在且为 RGBA。
3. 视觉上主体被正确抠出（允许边缘轻微误差）。

---

## 建议提交节奏
1. `feat(core): add model manager and local-only model loading`
2. `feat(ui): add model download page and startup model gate`
3. `test: add model gate/download coverage and matting regressions`
4. `docs: record manual e2e verification with fixed sample image`

