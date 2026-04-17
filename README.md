# Folder Poster Tool

一个基于 PyQt6 的桌面工具：从本地文件夹批量挑选图片/视频帧，进行 BiRefNet 抠图，并导出为可继续编辑的 PSD。

## 功能概览

- 文件夹扫描：按模式扫描视频或图片素材，支持递归层级
- 素材选择：
  - 视频模式：抽帧选择
  - 图片模式：直接多选
- 批量抠图：使用 BiRefNet 生成前景结果
- PSD 导出：固定 2:3 画布，图层默认隐藏，居中堆叠
- 模型下载：首次使用引导下载模型到本地

## 环境要求

- Python 3.11+（本地开发）
- macOS / Windows
- FFmpeg（视频抽帧依赖）
- 建议使用项目虚拟环境 `.venv`

## 本地开发

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## 测试（必须走 .venv）

项目约定统一用以下入口执行测试：

```bash
./scripts/test.sh
```

也可以执行单测：

```bash
./scripts/test.sh tests/test_packaging_ci.py -q
```

## 打包与发布

已支持 GitHub Actions 双平台打包（Windows + macOS Apple Silicon）：

- 工作流文件：`.github/workflows/build.yml`
- 触发方式：`v*` 标签推送 或 手动触发 `workflow_dispatch`
- Windows：自动分卷压缩（超大包时生成 `.zip.001` 等）
- macOS：输出 `Folder-Poster-macOS-ARM.zip`

详细操作见：`docs/release/build-and-release.md`

## v0.0.1 说明

`v0.0.1` 为首个发布版本，包含：

- 初始 README 与发布说明
- PyInstaller 打包配置 `folder-poster.spec`
- GitHub CI 自动打包与 Release 上传流程
- 打包流程契约测试 `tests/test_packaging_ci.py`

