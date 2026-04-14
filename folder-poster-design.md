# Folder Poster 设计文档

## 1. 产品流程

### 1.1 核心流程

```
输入：本地文件夹路径 + 模式（视频/图片）+ 递归深度（默认3，最大10）
    ↓
扫描文件夹 ──→ 递归查找所有视频 或 所有图片
    ↓
素材选取页面 ──→ 列表展示所有找到的文件（带预览）
    ↓
视频模式：点击视频 → Modal 生成32张等分截屏
          多选保留 → 确定
          重新生成 → 随机生成32张（已选中的保留，只生成未选中的）
    ↓
图片模式：直接多选图片
    ↓
批量抠像（BiRefNet）
    ↓
导出 PSD ──→ 2:3 画布
          所有抠像素材作为图层
          所有图层默认隐藏（关闭）
          图层堆叠在中间位置
    ↓
结束（无项目保存概念）
```

### 1.2 功能细节

#### 输入参数
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| 文件夹路径 | string | 必填 | 本地绝对路径 |
| 模式 | enum | 必填 | video / image |
| 递归深度 | int | 3 | 1-10 |

#### 文件扫描规则
- **视频模式**：递归查找 `.mp4`, `.mkv`, `.avi`, `.mov` 等视频文件
- **图片模式**：递归查找 `.jpg`, `.jpeg`, `.png`, `.webp` 等图片文件
- 递归深度可配置，默认3层，最大10层

#### 视频截屏规则
- **首次生成**：将视频等分为32段，取每段中点帧
- **重新生成**：随机生成32个时间点取帧
- **保留机制**：用户已选中的帧，重新生成时保留，只替换未选中的帧
- **多选支持**：用户可多选帧，作为该视频的素材

#### 抠像输出
- 输入：用户选中的图片（视频截屏或原始图片）
- 输出：透明背景 PNG
- 模型：BiRefNet

#### PSD 规范
- **画布比例**：固定 2:3
- **画布分辨率**：可配置，默认 2000x3000px
- **图层**：每张抠像图作为一个独立图层
- **图层状态**：默认全部隐藏（不可见）
- **图层位置**：全部堆叠在画布中心
- **图层类型**：普通图层（非智能对象）

### 1.3 用户交互流程

#### 视频模式
1. 用户选择文件夹，设置递归深度，进入素材选取页
2. 页面展示所有找到的视频列表（缩略图+文件名）
3. 用户点击某个视频，弹出 Modal
4. Modal 中展示32张等分截屏，用户多选需要的帧
5. 点击"重新生成"，已选中的帧保留，其余32张随机替换
6. 点击"确定"，该视频的选中帧加入素材池
7. 重复步骤3-6，处理其他视频
8. 点击"下一步"，进入抠像流程

#### 图片模式
1. 用户选择文件夹，设置递归深度，进入素材选取页
2. 页面展示所有找到的图片列表（缩略图+文件名）
3. 用户多选需要的图片
4. 点击"下一步"，进入抠像流程

#### 抠像与导出
1. 展示批量抠像进度
2. 抠像完成后，展示预览（可选）
3. 用户点击"导出 PSD"
4. 生成 PSD 文件，保存到指定位置
5. 结束

---

## 2. 技术架构

### 2.1 技术选型

| 组件 | 选型 | 说明 |
|------|------|------|
| 桌面框架 | PyQt6 | 纯 Python，性能高，跨平台 |
| 视频处理 | ffmpeg (subprocess) | 提取视频帧 |
| 抠像模型 | BiRefNet | 本地加载，GPU 推理 |
| PSD 生成 | pytoshop | 轻量，只写不读 |
| 图像处理 | Pillow (PIL) | 图像加载、缩放、格式转换 |

### 2.2 系统架构

```
┌─────────────────────────────────────────┐
│           PyQt6 桌面应用                 │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐ │
│  │ 素材选取 │  │ 截屏Modal│  │ 抠像进度 │ │
│  │   页面  │  │   页面  │  │   页面  │ │
│  └────┬────┘  └────┬────┘  └────┬────┘ │
│       └─────────────┴─────────────┘      │
│                      │                   │
│         ┌────────────┴────────────┐      │
│         │       核心引擎           │      │
│         ├─ scanner.py   递归文件扫描    │
│         ├─ extractor.py 视频截屏(ffmpeg)│
│         ├─ matting.py   抠像(BiRefNet)  │
│         └─ psd_export.py PSD生成        │
│                      │                   │
│         ┌────────────┴────────────┐      │
│         │      数据模型            │      │
│         ├─ Project  临时项目数据    │
│         ├─ Video    视频+选中帧     │
│         ├─ Image    图片素材        │
│         └─ Material 最终抠像素材    │
└─────────────────────────────────────────┘
```

### 2.3 模块职责

| 模块 | 文件 | 职责 |
|------|------|------|
| 文件扫描 | `scanner.py` | 递归扫描文件夹，按模式过滤视频/图片 |
| 视频截屏 | `extractor.py` | ffmpeg 提取视频帧，等分32或随机32 |
| 抠像引擎 | `matting.py` | BiRefNet 模型加载与推理，批量抠像 |
| PSD 导出 | `psd_export.py` | pytoshop 生成 PSD，2:3画布，隐藏图层 |
| 数据模型 | `models.py` | Project/Video/Image/Material 类定义 |
| UI 页面 | `ui/` | PyQt6 界面实现 |

### 2.4 依赖清单

```
PyQt6>=6.4.0
birefnet>=1.0.0
torch>=2.0.0
torchvision>=0.15.0
pillow>=9.0.0
pytoshop>=1.2.0
```

---

## 3. 界面设计与交互流程

### 3.1 页面清单

| 页面 | 说明 |
|------|------|
| 首页 | 输入文件夹路径、选择模式、设置递归深度 |
| 素材选取页 | 视频列表或图片列表，选择素材 |
| 截屏 Modal | 视频模式专用，32张截屏选择 |
| 抠像进度页 | 批量处理，显示进度和结果 |
| 完成页 | 导出 PSD，选择保存路径 |

### 3.2 首页

```
┌─────────────────────────────────────┐
│           Folder Poster             │
├─────────────────────────────────────┤
│                                     │
│   文件夹路径: [________________] [浏览] │
│                                     │
│   模式:  (○) 视频模式   ( ) 图片模式  │
│                                     │
│   递归深度: [ 3 ] 层  (1-10)        │
│                                     │
│                                     │
│           [   开始扫描   ]           │
│                                     │
└─────────────────────────────────────┘
```

**元素说明：**
- 文件夹路径：文本输入框，支持拖拽文件夹，[浏览] 按钮打开文件选择器
- 模式：单选按钮，视频模式 / 图片模式
- 递归深度：数字输入框，范围 1-10，默认 3
- 开始扫描：进入素材选取页

**交互：**
- 路径输入框支持拖拽文件夹自动填充
- 模式切换时，下方可显示对应提示文字
- 路径为空时，开始扫描按钮禁用

### 3.3 素材选取页（视频模式）

```
┌─────────────────────────────────────────────────────┐
│  ← 返回                    Folder Poster    [下一步] │
├─────────────────────────────────────────────────────┤
│  已找到 12 个视频文件（递归 3 层）                      │
│                                                     │
│  [瀑布流 ▼]  [大小: ████████░░]                     │
│                                                     │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│  │ ▶️ 预览  │ │ ▶️ 预览  │ │ ▶️ 预览  │ │ ▶️ 预览  │  │
│  │ video1  │ │ video2  │ │ video3  │ │ video4  │  │
│  │ ✅已选3帧│ │         │ │ ✅已选5帧│ │         │  │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘  │
│  ┌─────────┐ ┌─────────┐ ...                       │
│  │ ...     │ │ ...     │                           │
│  └─────────┘ └─────────┘                           │
│                                                     │
│  已选素材: 8 帧（来自 3 个视频）                      │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**元素说明：**
- 返回按钮：回到首页
- 下一步按钮：进入抠像进度页（至少选一个素材才可点击）
- 视图模式切换：瀑布流 / 等宽等高
- 大小滑块：调整缩略图大小，有最大最小阈值
- 视频卡片：预览按钮、文件名、已选帧数（0帧不显示）
- 底部统计：已选素材总数

**交互：**
- 点击视频卡片打开截屏 Modal
- 已选帧数 > 0 的卡片高亮显示
- 缩略图点击放大预览
- 瀑布流模式：保持原始比例
- 等宽等高模式：统一尺寸裁剪

### 3.4 截屏 Modal（视频模式）

```
┌─────────────────────────────────────────────────────┐
│  video1.mp4                              [X] 关闭   │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ...    │
│  │ ✅ │ │    │ │ ✅ │ │    │ │ ✅ │ │    │         │
│  │帧1 │ │帧2 │ │帧3 │ │帧4 │ │帧5 │ │帧6 │         │
│  └────┘ └────┘ └────┘ └────┘ └────┘ └────┘         │
│  ...                                                │
│                                                     │
├─────────────────────────────────────────────────────┤
│  已选: 3/32                                        │
│                                                     │
│  [重新生成]  [清空选择]              [确定]          │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**元素说明：**
- Modal 标题：视频文件名
- 关闭按钮：关闭 Modal
- 截屏网格：32 张截屏，比例跟随视频比例
- 已选标记：✅ 标记，边框高亮
- 底部统计：已选数量 / 总数
- 重新生成：保留已选，随机替换未选
- 清空选择：全部取消选择
- 确定：保存选择，关闭 Modal

**交互：**
- 点击截屏切换选中/取消
- 截屏点击放大预览
- Modal 可缩放调整大小
- 重新生成无确认提示
- 首次生成：等分 32 段取帧
- 重新生成：随机 32 个时间点取帧

### 3.5 素材选取页（图片模式）

```
┌─────────────────────────────────────────────────────┐
│  ← 返回                    Folder Poster    [下一步] │
├─────────────────────────────────────────────────────┤
│  已找到 45 张图片（递归 3 层）                         │
│                                                     │
│  [瀑布流 ▼]  [大小: ████████░░]                     │
│                                                     │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│  │         │ │         │ │         │ │         │  │
│  │  img1   │ │  img2   │ │  img3   │ │  img4   │  │
│  │  ✅已选  │ │         │ │  ✅已选  │ │         │  │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘  │
│  ...                                                │
│                                                     │
│  已选素材: 12 张                                     │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**元素说明：**
- 与视频模式类似，但无"预览"按钮
- 图片卡片：缩略图、文件名、选中状态

**交互：**
- 点击图片切换选中/取消
- 选中图片高亮显示
- 缩略图点击放大预览

### 3.6 抠像进度页

```
┌─────────────────────────────────────────────────────┐
│  [进度条: ████████████████████░░░░░░  45%]           │
│  正在处理: img_05.png    剩余: 15/28                 │
├──────────────────────────┬──────────────────────────┤
│                          │                          │
│    原始素材区             │    抠像结果区             │
│                          │                          │
│  ┌────────┐ ┌────────┐  │  ┌────────┐ ┌────────┐   │
│  │ img_01 │ │ img_02 │  │  │ [抠像] │ │ ✅ done │   │
│  │ ✅done │ │ ⏳wait │  │  │        │ │        │   │
│  └────────┘ └────────┘  │  └────────┘ └────────┘   │
│  ┌────────┐ ┌────────┐  │  ┌────────┐ ┌────────┐   │
│  │ img_03 │ │ img_04 │  │  │ ✅ done│ │ ⏳wait │   │
│  │ ✅done │ │ ❌fail │  │  │        │ │        │   │
│  └────────┘ └────────┘  │  └────────┘ └────────┘   │
│  ...                     │  ...                     │
│                          │                          │
├──────────────────────────┴──────────────────────────┤
│  [取消]                              [导出 PSD]    │
└─────────────────────────────────────────────────────┘
```

**元素说明：**
- 顶部：进度条、当前文件名、剩余数量
- 左侧：原始素材列表，带状态标记
  - ⏳ 等待中
  - 🔄 处理中
  - ✅ 已完成
  - ❌ 失败
- 右侧：抠像结果预览
  - 处理中：loading 动画
  - 已完成：显示抠像结果
  - 失败：红色标记
- 底部：取消按钮、导出 PSD 按钮（完成后可用）

**交互：**
- 左右区域独立滚动
- 所有图片点击放大预览
- 失败项点击自动重试
- 取消按钮：中断处理，返回素材选取页
- 导出 PSD 按钮：进入完成页

### 3.7 完成页

```
┌─────────────────────────────────────────────────────┐
│  ← 返回                    Folder Poster             │
├─────────────────────────────────────────────────────┤
│                                                     │
│              ✅ 抠像完成                             │
│                                                     │
│         共 28 张素材，全部处理成功                    │
│                                                     │
│  保存位置: [_________________________] [浏览]       │
│            默认: 输入文件夹路径                       │
│                                                     │
│  画布尺寸: [ 4000 x 6000 ▼ ] px（2:3）              │
│            选项: 4000x6000 / 2000x3000 / 自定义      │
│                                                     │
│           [   导出 PSD   ]                          │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**元素说明：**
- 完成状态：✅ 抠像完成，统计信息
- 保存位置：文本输入框，默认输入文件夹路径，[浏览] 可修改
- 画布尺寸：下拉选择，默认 4000x6000，选项：4000x6000、2000x3000、自定义
- 导出 PSD 按钮：生成 PSD 文件

**交互：**
- 导出完成后自动打开文件夹
- 返回按钮：回到抠像进度页

### 3.8 通用交互

**图片放大预览：**
- 所有页面的图片点击都可放大预览
- 放大视图支持缩放、拖拽、关闭

**状态颜色：**
- 已选/完成：绿色/蓝色高亮
- 失败：红色标记
- 等待/未选：灰色

---

## 4. 技术流程

### 4.1 整体流程

```
用户输入：文件夹路径 + 模式 + 递归深度
    ↓
1. 文件扫描 (scanner.py)
    - os.walk 递归遍历，限制深度
    - 按扩展名过滤（视频/图片）
    - 生成文件列表，写入 temp json
    ↓
2. 素材选取 (UI)
    - 视频模式：
        - 点击视频 → 检查缓存（视频路径hash+序号）
        - 缓存存在：直接读取32帧
        - 缓存不存在：ffmpeg提取32帧，保存缓存
        - 用户多选 → 保存选中状态到temp json
        - 重新生成：保留已选帧，随机替换未选帧
    - 图片模式：
        - 用户多选图片 → 保存选中状态到temp json
    ↓
3. 批量抠像 (matting.py)
    - 首次抠像：加载BiRefNet模型
    - 遍历选中素材：
        - 检查matte_map：source_id + mtime匹配且is_active=true → 跳过
        - 不匹配或is_active=false → 执行抠像
        - 保存结果：{原文件名}_matte.png
        - 更新matte_map记录
    - 返回上一步时：
        - 对比选中列表变化
        - 取消的：is_active=false
        - 新增的：检查记录，存在则is_active=true，否则新抠
    ↓
4. PSD生成 (psd_export.py)
    - pytoshop创建2:3画布（默认4000x6000）
    - 遍历matte_map中is_active=true的记录
    - 每张PNG作为图层插入，图层名：文件夹名_时间戳
    - 所有图层隐藏，位置居中
    - 保存PSD到指定路径
    ↓
5. 完成：打开文件夹
    - 退出时：清空缓存目录 ~/.folder-poster/cache/
    - 保留temp json（供下次继续？）或删除
```

### 4.2 缓存策略

**缓存目录**：`~/.folder-poster/cache/`

| 缓存类型 | 命名规则 | 生命周期 |
|----------|----------|----------|
| 视频帧 | `{视频路径hash}_{序号}.jpg` | 退出时清空 |
| 抠像结果 | `{原文件名}_matte.png` | 退出时清空 |

**视频帧缓存逻辑**：
- 视频路径hash = MD5(绝对路径)
- 打开Modal时：检查 `cache/{hash}_00.jpg` 是否存在
- 存在：直接读取32帧
- 不存在：ffmpeg提取，保存到缓存
- 重新生成：只替换未选中的帧（序号不在已选列表中的）

### 4.3 状态管理

**Temp JSON 路径**：`~/.folder-poster/temp/{项目ID}.json`

**结构**：
```json
{
  "project_id": "proj_abc123",
  "input_path": "/path/to/folder",
  "mode": "video",
  "depth": 3,
  "scanned_files": [
    {"path": "...", "name": "video1.mp4", "type": "video"}
  ],
  "selected_materials": [
    {"source_id": "vid_xxx", "frame_idx": 5, "selected": true}
  ],
  "matte_map": [
    {
      "source_id": "vid_xxx_frame_05",
      "source_mtime": 1713091200,
      "matte_path": "cache/vid_xxx_frame_05_matte.png",
      "is_active": true
    }
  ],
  "current_step": "matting"
}
```

**状态流转**：
- 首页 → 素材选取：创建temp json，写入scanned_files
- 素材选取 → 抠像：更新selected_materials
- 抠像进度：更新matte_map，current_step
- 返回上一步：读取temp json恢复状态，对比更新matte_map

### 4.4 错误处理

| 错误场景 | 处理策略 |
|----------|----------|
| 文件扫描失败 | 提示错误，记录日志 |
| ffmpeg提取失败 | 标记该视频失败，跳过继续 |
| 抠像失败 | matte_map标记失败，UI红色显示，支持点击重试 |
| PSD生成失败 | 提示错误，保留抠像结果，可重试导出 |

### 4.5 性能考虑

- **懒加载**：BiRefNet模型第一次抠像时才加载
- **顺序处理**：单线程顺序抠像，避免GPU内存爆炸
- **文件操作**：图片以文件路径传递，不全部加载到内存
- **缓存复用**：视频帧和抠像结果智能复用，避免重复计算

## 5. BiRefNet 集成方案（参考 birefnet-gui）

### 5.1 参考项目路径

```
/Users/liujiahao/OthDev/birefnet-gui
├── src/core/inference.py      # 核心：模型加载与推理
├── src/core/config.py         # 模型配置
├── src/core/device_info.py    # 设备检测
└── models/                    # 模型文件目录
```

### 5.2 需要复制的文件

**复制到本项目的 `core/birefnet/` 目录：**

| 源文件 | 目标路径 | 说明 |
|--------|----------|------|
| `src/core/inference.py` | `core/birefnet/inference.py` | 核心推理代码，复制后删除 `predict_batch`（只用单张） |
| `src/core/device_info.py` | `core/birefnet/device_info.py` | 设备检测（CUDA/MPS/CPU） |
| `src/core/config.py` | `core/birefnet/config.py` | 模型配置，简化后使用 |

### 5.3 代码调整

**`inference.py` 调整：**
```python
# 删除 predict_batch 函数（只用 predict 单张推理）
# 调整导入路径：
# from src.core.config import MODELS  →  from core.birefnet.config import MODELS
# from src.core.device_info import detect_device  →  from core.birefnet.device_info import detect_device
```

**`config.py` 简化：**
```python
# 只保留 BiRefNet 模型配置
MODELS = {
    "BiRefNet": "birefnet",
}

# 模型路径：~/.folder-poster/models/birefnet/
```

**`device_info.py`：无需修改，直接使用**

### 5.4 模型文件准备

**模型目录结构：**
```
~/.folder-poster/models/
└── birefnet/
    ├── config.json
    ├── model.safetensors
    ├── preprocessor_config.json
    └── ...（其他模型文件）
```

**模型下载：**
- 参考 `birefnet-gui/download_models.py` 实现自动下载
- 或手动从 HuggingFace 下载 `ZhengPeng7/BiRefNet` 放到上述目录

### 5.5 使用示例

```python
from core.birefnet.inference import load_model, predict, detect_device
from core.birefnet.config import get_model_path
import numpy as np
from PIL import Image

# 初始化（首次抠像时调用）
model_path = get_model_path("BiRefNet", "~/.folder-poster/models")
device = detect_device()  # 自动返回 cuda / mps / cpu
model = load_model(model_path, device)

# 抠像（循环处理每张图）
image = Image.open("input.jpg")
frame = np.array(image)  # RGB numpy array
alpha = predict(model, frame, device, resolution=1024)  # 返回 alpha mask

# 合成透明PNG
rgba = np.dstack((frame, alpha))
result = Image.fromarray(rgba, 'RGBA')
result.save("output_matte.png")
```

### 5.6 跨平台支持

| 平台 | 设备 | 说明 |
|------|------|------|
| Windows | CUDA (NVIDIA) | 自动检测，使用 float16 加速 |
| macOS | MPS (Apple Silicon) | 自动检测，使用 float32 |
| 其他 | CPU | 自动降级，较慢但可用 |

### 5.7 性能优化

- **分辨率**：默认 1024，可在设置中调整（512/1024/2048）
- **模型缓存**：`load_model` 只调用一次，后续复用
- **显存管理**：单张推理，不 batch，避免 OOM

## 6. 实现里程碑

### 6.1 第一期：功能开发

| 阶段 | 内容 | 预计时间 |
|------|------|----------|
| 1. 基础框架 | PyQt6 项目搭建，页面导航，基础UI布局 | 2-3天 |
| 2. 文件扫描 | 递归扫描，文件过滤，缓存目录创建 | 1天 |
| 3. 素材选取-图片 | 图片列表，瀑布流/等高等宽，选中状态 | 2天 |
| 4. 素材选取-视频 | 视频列表，ffmpeg截屏，Modal，缓存逻辑 | 3天 |
| 5. BiRefNet集成 | 复制参考代码，模型加载，抠像流程 | 2天 |
| 6. PSD导出 | pytoshop集成，图层生成，画布设置 | 2天 |
| 7. 状态管理 | temp json，上一步/下一步状态恢复 | 2天 |
| 8. 细节优化 | 图片预览，错误处理，UI polish | 2-3天 |
| **总计** | | **约2周** |

**风险缓冲**：+1周（环境配置、跨平台兼容性、UI调整）

**第一期交付标准**：
- [ ] Windows / macOS 可运行（Python源码）
- [ ] 图片模式完整流程
- [ ] 视频模式完整流程
- [ ] 缓存机制正常工作
- [ ] 状态管理（上一步/下一步）正常

### 6.2 第二期：打包发布

**目标**：PyInstaller 打包 + GitHub Actions 自动构建

| 阶段 | 内容 | 预计时间 |
|------|------|----------|
| 1. PyInstaller 配置 | 编写 .spec 文件，测试本地打包 | 2天 |
| 2. 模型下载器 | 首次启动自动下载 BiRefNet 模型 | 1天 |
| 3. FFmpeg 检测 | 启动时检测系统 FFmpeg，提示安装 | 1天 |
| 4. GitHub Actions | 配置 Windows / macOS 自动构建 | 2天 |
| 5. 发布流程 | Release 自动上传，版本管理 | 1天 |
| **总计** | | **约1周** |

**打包策略（参考 birefnet-gui）：**

| 项目 | 方案 | 说明 |
|------|------|------|
| 打包工具 | PyInstaller | `--onedir` 文件夹模式 |
| 模型文件 | 首次下载 | 不打包，减小体积，启动时从 HuggingFace 下载 |
| FFmpeg | 用户安装 | 启动时检测，未安装提示下载安装 |
| 分卷压缩 | 不需要 | 直接 zip 压缩 |
| 代码签名 | 暂不需要 | 用户手动允许即可 |

**PyInstaller 关键配置：**

```python
# folder-poster.spec
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

transformers_datas = collect_data_files("transformers", includes=["**/*.json"])

hidden = [
    "einops",
    "kornia", 
    "timm",
    "PIL",
    "pytoshop",
]
hidden += collect_submodules("transformers.models.bit")

a = Analysis(
    ["main.py"],
    datas=transformers_datas,
    hiddenimports=hidden,
    excludes=["matplotlib", "tkinter", "jupyter", "notebook", "pytest"],
    noarchive=False,
)

# 模型下载目录
model_dir = os.path.expanduser("~/.folder-poster/models")
```

**GitHub Actions 工作流：**

```yaml
# .github/workflows/build.yml
name: Build Release
on:
  push:
    tags: ['v*']
jobs:
  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install pyinstaller -r requirements.txt
      - run: pyinstaller folder-poster.spec
      - run: 7z a Folder-Poster-Windows.zip dist/Folder-Poster
      - uses: actions/upload-release-asset@v1
        with:
          asset_path: ./Folder-Poster-Windows.zip
  
  build-macos:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install pyinstaller -r requirements.txt
      - run: pyinstaller folder-poster.spec
      - run: zip -r Folder-Poster-macOS.zip dist/Folder-Poster.app
      - uses: actions/upload-release-asset@v1
        with:
          asset_path: ./Folder-Poster-macOS.zip
```

**第二期交付标准：**
- [ ] Windows 可执行文件（zip）
- [ ] macOS 应用程序（zip）
- [ ] 首次启动自动下载模型
- [ ] FFmpeg 检测与提示
- [ ] GitHub Actions 自动构建
- [ ] Release 页面发布
