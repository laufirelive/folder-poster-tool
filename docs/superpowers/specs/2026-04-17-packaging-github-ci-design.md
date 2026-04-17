# GitHub CI 双平台打包设计（macOS ARM + Windows）

## 1. 背景与目标

当前 `folder-poster-tool` 尚未落地可执行的 GitHub CI 打包流程，项目已有“二期打包发布”目标与草案，但缺少可直接执行的配置文件。

本设计目标：

1. 复用 `birefnet-gui` 的成熟经验，在本项目新增可执行 CI 打包链路。
2. 通过 `v*` tag 自动构建并发布两个版本：
   - macOS Apple Silicon（arm64）
   - Windows
3. Windows 包体超过阈值时自动分卷，避免 GitHub 资产大小限制导致发布失败。

## 2. 约束与确认项

已确认约束：

1. macOS 仅支持 Apple Silicon（arm64）。
2. 正式发布触发方式为 `push tags: v*`。
3. Windows 使用自动分卷策略（`*.zip.001` 等）。

兼容性约束：

1. 继续使用当前应用入口 `main.py` 与 `PyQt6` 桌面形态。
2. 模型不内置在安装包内，保持首次下载策略。
3. FFmpeg 不内置，使用运行时检测与安装提示。

## 3. 方案对比

### 方案 A（推荐）：单 workflow + matrix

- 一个 `.github/workflows/build.yml`，通过 matrix 同时构建 macOS 与 Windows。
- 优点：配置集中、维护成本低、与 `birefnet-gui` 路径一致。
- 缺点：单文件可读性中等。

### 方案 B：双 workflow 拆分

- 分成 `build-windows.yml` 和 `build-macos.yml`。
- 优点：定位平台问题更直观。
- 缺点：重复配置较多，版本升级改动点翻倍。

### 方案 C：可复用 workflow（workflow_call）

- 顶层触发器 + 可复用子流程。
- 优点：结构化最佳，适合大团队长期演进。
- 缺点：当前规模下复杂度偏高。

结论：采用方案 A。

## 4. 推荐方案详细设计

## 4.1 Workflow 结构

新增文件：`.github/workflows/build.yml`

触发器：

1. `push.tags: ["v*"]`（正式发布）
2. `workflow_dispatch`（手动验证/紧急构建）

权限：

- `contents: write`（用于上传 Release 资产）

Job 设计：

1. 单 `build` job，`strategy.matrix` 包含两个平台：
   - `windows-latest` / `artifact=Folder-Poster-Windows`
   - `macos-latest` / `artifact=Folder-Poster-macOS-ARM`
2. Python 版本统一 `3.11`。
3. 构建流程：
   - checkout
   - setup python
   - 安装依赖（`requirements.txt` + `pyinstaller`）
   - 执行 `pyinstaller folder-poster.spec`
   - 在 `dist/Folder-Poster` 生成 `README.txt`
   - 压缩产物（Windows 分卷，mac 直 zip）
   - `upload-artifact`
   - tag 场景下 `softprops/action-gh-release@v2` 上传 Release

## 4.2 PyInstaller 设计

新增文件：`folder-poster.spec`

关键策略：

1. 构建模式：`--onedir`。
2. 入口：`main.py`。
3. 目标名：`Folder-Poster`。
4. `datas`：收集 `transformers` 运行期 JSON 配置。
5. `hiddenimports`：
   - `einops`, `kornia`, `timm`, `PIL`, `huggingface_hub`
   - `collect_submodules("transformers.models.bit")`
6. `excludes`：去掉测试与无关开发依赖（如 `pytest`, `jupyter`, `IPython` 等）以减小体积。

## 4.3 打包内容边界

安装包包含：

1. 可执行程序（`Folder-Poster` 或 `Folder-Poster.exe`）
2. 运行期所需 python 依赖与动态库
3. `README.txt`（运行说明）

安装包不包含：

1. BiRefNet 模型权重（首次下载）
2. FFmpeg（二进制由用户安装）
3. 测试与开发工具链

## 4.4 Release 与命名规范

Release 资产命名：

1. `Folder-Poster-Windows.zip`（超限时为 `Folder-Poster-Windows.zip.001` 等分卷）
2. `Folder-Poster-macOS-ARM.zip`

规则：

1. 两平台都成功再视为完整发布结果。
2. 任一平台失败，workflow 直接失败并保留日志。
3. 所有构建产物先上传 workflow artifact，再上传 release 资产，确保可追溯。

## 4.5 可观测性与失败处理

CI 日志需明确输出：

1. PyInstaller 输出目录与文件清单。
2. 压缩后文件名与大小。
3. 上传到 artifact/release 的最终文件列表。

失败处理：

1. 依赖安装失败：直接失败并保留 pip 输出。
2. PyInstaller 构建失败：直接失败并输出构建日志。
3. 压缩失败：直接失败，保留压缩命令错误信息。
4. Release 上传失败：保留 artifact，便于后续人工下载与复核。

## 5. README 运行说明要求

`dist/Folder-Poster/README.txt` 至少包含：

1. FFmpeg 安装方式（Windows/macOS）
2. 首次启动需要下载模型
3. 常见运行提示（系统安全拦截、解压后再运行）

## 6. 验收标准

1. 打 `v*` tag 后，GitHub Actions 自动触发并完成双平台构建。
2. Release 页面可下载 Windows 与 macOS ARM 产物。
3. Windows 包体超限时自动分卷并可正常解压。
4. 解压后应用可启动到主界面。
5. 首次启动模型下载流程正常；未安装 FFmpeg 时有可理解提示。

## 7. 测试与验证计划

本地验证：

1. 在本机执行 `pyinstaller folder-poster.spec` 验证 spec 基本可用。
2. 通过项目约定脚本在 `.venv` 下跑测试：`./scripts/test.sh`。

CI 验证：

1. 先用 `workflow_dispatch` 进行一次试跑。
2. 再通过测试 tag（如 `v0.0.1-test`）验证 release 上传路径。

## 8. 风险与缓解

1. 风险：不同平台的 `torch` 安装耗时与失败率较高。
   - 缓解：保持失败即失败，必要时后续引入 pip 缓存优化。
2. 风险：PyInstaller 隐式依赖遗漏导致运行时崩溃。
   - 缓解：首版按 `birefnet-gui` hiddenimports 起步，按报错补齐。
3. 风险：Windows 包体持续增长。
   - 缓解：保留分卷策略并持续优化 excludes 列表。

## 9. 实施范围声明

本设计只覆盖“打包与发布链路落地”，不包含：

1. 应用功能改造
2. 代码签名与公证
3. 自动更新器

