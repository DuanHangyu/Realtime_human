<div align="center">
  <img src="images/LOGO.png" alt="Realtime Human Logo" width="400">

# Realtime Human

**实时交互数字人系统，支持语音对话**

开源全栈数字人平台。上传一段视频，制作数字人角色，即可在浏览器中进行实时语音对话。客户端无需 GPU。

[中文](#功能特性) | [English](README.md)

</div>

<div align="center">
  <img src="images/zhutu.png" alt="Realtime Human - 对话界面" width="800">
</div>

<div align="center">
  <img src="images/demo_readme.gif" alt="演示动画" width="800">
</div>

https://github.com/user-attachments/assets/5aaf672b-5090-4ef5-a014-f160668dffce

---

## 功能特性

- **一键制作数字人** — 上传一段人脸视频，训练管道自动提取面部关键点、构建3D网格、生成动画数据
- **实时语音对话** — 对着数字人说话，获得流式音频+文本回复，由 ASR + LLM + TTS 驱动
- **无GPU浏览器渲染** — WebGL + WASM 实时渲染说话人脸，在任何现代浏览器中运行
- **多角色切换** — 创建和部署多个数字人角色，即时切换
- **全栈开源** — 前端（React + WebGL）、训练服务器（FastAPI + PyTorch）、语音后端（.NET 9），全部包含

## 平台展示

<div align="center">
  <img src="images/peitu.png" alt="平台功能展示" width="800">
</div>

## 系统架构

```
                         ┌──────────────────────┐
                         │      用户浏览器        │
                         │  ┌────────────────┐   │
                         │  │ React + WebGL  │   │
                         │  │ + WASM 模块    │   │
                         │  └───────┬────────┘   │
                         └──────────┼─────────────┘
                          WebSocket │     HTTP
                      ws://*:19465  │  http://*:5173
                                    │
                 ┌──────────────────┴───────────────────┐
                 │                                      │
        ┌────────▼────────┐                   ┌─────────▼─────────┐
        │   语音服务器     │                   │   React 前端      │
        │   (.NET 9)      │                   │   (Vite 开发)     │
        │                 │                   │                   │
        │ ASR → LLM → TTS │                   │ WebGL 人脸渲染    │
        └───┬────┬────┬───┘                   │ WASM 音频处理     │
            │    │    │                        │ 聊天界面          │
            │    │    │                        └───────────────────┘
            ▼    ▼    ▼
        ┌─────┐┌───┐┌─────┐
        │FunASR││LLM││ TTS │
        │(语音 ││大 ││(语音│
        │识别) ││模型││合成)│
        └─────┘└───┘└─────┘


    ── 角色训练流程 ──────────────────────────────────

    ┌──────────────┐    上传视频        ┌──────────────────┐
    │  管理员浏览器  │ ────────────────  │   训练服务器      │
    │  (端口 8000)  │ ◄── SSE 进度推送 ── │   (FastAPI)      │
    └──────────────┘                      │                  │
                                          │ 6 步管道：        │
                                          │  1. 视频 → 25fps  │
                                          │  2. 面部关键点     │
                                          │  3. 嘴部裁剪      │
                                          │  4. 3D 网格生成   │
                                          │  5. DINet 特征    │
                                          │  6. 打包 gzip     │
                                          └────────┬─────────┘
                                                   │ 部署
                                                   ▼
                                          ┌──────────────────┐
                                          │ characters/ 目录  │
                                          │  01.mp4          │
                                          │  data (gzip)     │
                                          │  preview.jpg     │
                                          └──────────────────┘
```

## 快速开始

> **开始之前，先了解两个概念：**
> - **制作数字人角色** = 上传一段人脸视频，管道使用预训练模型生成动画数据（每个角色约 2MB）。不需要训练模型。
> - **从零训练模型** = 从头训练 DINet / LSTM 模型权重。只有需要自定义模型时才需要。参见 [高级：从零训练模型](#高级从零训练模型)。

### 前置条件

| 依赖 | 版本 | 用途 |
|------|------|------|
| Python | 3.11+ | 角色制作管道 |
| Node.js | 18+ | 前端 |
| .NET SDK | 9.0 | 语音后端服务器 |
| FFmpeg | 任意版本 | 视频处理（需加入 PATH） |

### 1. 克隆项目

```bash
git clone https://github.com/your-username/Realtime_human.git
cd Realtime_human
```

### 2. 下载预训练模型权重

角色制作管道需要预训练模型权重。下载后放置到 `dhy_human/checkpoint/`：

```
dhy_human/checkpoint/
├── DINet_mini/
│   └── epoch_40.pth              # DINet 渲染模型
├── lstm/
│   └── lstm_model_epoch_325.pkl  # 音频到表情的 LSTM 模型
├── audio.pkl                     # 音频特征模型
└── pca.pkl                       # PCA 降维模型（用于表情分解）
```

这些模型参照 [DH_live](https://github.com/kleinlee/DH_live) 的方法训练，适用于任何人脸视频。如需自行训练，参见 [高级：从零训练模型](#高级从零训练模型)。

### 3. 启动角色制作服务器

```bash
cd dhy_human

# 创建 conda 环境（推荐）
conda create -n realtime_human python=3.11
conda activate realtime_human

# 安装依赖
pip install torch --index-url https://download.pytorch.org/whl/cu124   # GPU 版
# 或者：pip install torch                                               # CPU 版
pip install -r requirements.txt
pip install -r living_human/training_server/requirements.txt

# 启动服务器
cd living_human/training_server
python server.py
```

角色制作服务器运行在 http://localhost:8000。

### 4. 启动语音服务器

打开新终端：

```bash
cd voice_server

# 复制配置模板，填入你的 API 密钥
cp appsettings.Example.json appsettings.json

# 安装依赖并启动
dotnet restore
dotnet run
```

编辑 `appsettings.json`，填入你的 API 密钥。各字段说明如下：

#### LLM — 大语言模型（聊天补全）

```json
"LLM": {
  "Model": "deepseek-v3-250324",
  "Token": "YOUR_VOLCENGINE_ARK_API_KEY",
  "ApiEndpoint": "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
}
```

| 字段 | 说明 |
|------|------|
| `Model` | 使用的模型名称（默认：火山引擎 ARK 上的 DeepSeek-V3） |
| `Token` | 聊天补全服务的 API 密钥 |
| `ApiEndpoint` | OpenAI 兼容的聊天补全接口地址 |

默认配置使用 [火山引擎 ARK](https://www.volcengine.com/product/ark)。你也可以使用任何 OpenAI 兼容的接口（如 DeepSeek 官方 API、本地 Ollama），只需修改 `ApiEndpoint` 和 `Token` 即可。

#### TTS — 语音合成

```json
"TTS": {
  "HuoShan": {
    "AppId": "YOUR_HUOSHAN_APP_ID",
    "Token": "YOUR_HUOSHAN_TOKEN"
  },
  "Clone": {
    "AppId": "YOUR_CLONE_APP_ID",
    "Token": "YOUR_CLONE_TOKEN"
  },
  "Coze": {
    "Key": ""
  },
  "DefaultVoiceType": "BV700_streaming"
}
```

| 字段 | 说明 |
|------|------|
| `TTS.HuoShan.AppId` / `Token` | [火山引擎 TTS](https://www.volcengine.com/product/tts) 凭证（必填，主要 TTS 后端） |
| `TTS.Clone.AppId` / `Token` | 语音克隆 TTS 凭证（可选，用于自定义声音克隆） |
| `TTS.Coze.Key` | [Coze](https://www.coze.com/) API 密钥（可选，备用 TTS 后端） |
| `DefaultVoiceType` | 默认语音类型 ID（如 `BV700_streaming`、`BV007_streaming`） |

#### Communication — 语音识别与服务器

```json
"Communication": {
  "FunasrUrl": "ws://YOUR_FUNASR_HOST:10095/",
  "ListenerPrefix": "http://+:19465/"
}
```

| 字段 | 说明 |
|------|------|
| `FunasrUrl` | [FunASR](https://github.com/modelscope/FunASR) WebSocket 地址，用于语音转文本 |
| `ListenerPrefix` | 语音服务器自身的监听地址（默认：所有网卡的 19465 端口） |

**FunASR 部署：** FunASR 是阿里达摩院开源的语音识别引擎。使用 Docker 部署最简单：

```bash
docker run -d -p 10095:10095 \
  registry.cn-hangzhou.aliyuncs.com/funasr_repo/funasr:funasr-runtime-sdk-online-cpu-0.1.12
```

FunASR 部署在本机则填 `ws://localhost:10095/`，部署在远程服务器则填 `ws://<服务器IP>:10095/`。

语音服务器监听 WebSocket 端口 19465。

### 5. 启动前端

再打开一个终端：

```bash
cd dhy_human/living_human/react-frontend

npm install
npm run dev
```

前端运行在 http://localhost:5173。

### 6. 制作你的数字人角色

1. 打开 http://localhost:8000（角色制作界面）
2. 上传一段人脸视频（MP4 格式，正面，单人，推荐 10 秒到 2 分钟）
3. 等待管道处理完成（6 个步骤，产出约 2MB 数据）
4. 点击**「部署」**，将角色推送到前端

### 7. 开始对话

1. 打开 http://localhost:5173（前端界面）
2. 从顶部选择器选择你的角色
3. 点击麦克风按钮说话，或在文本框中输入
4. 数字人将以同步的口型动画和语音进行回复

完成。你现在拥有了一个定制形象的实时语音对话数字人。

---

### 角色制作管道详情

上传视频后，管道通过 6 个步骤处理：

| 步骤 | 说明 | 关键操作 |
|------|------|---------|
| 1. 视频预处理 | 转换为 25fps，提取 478 个人脸关键点 | FFmpeg、MediaPipe FaceMesh |
| 2. 关键点平滑 | 加权移动平均滤波（权重：0.03, 0.1, 0.74, 0.1, 0.03） | Numpy 卷积 |
| 3. 嘴部裁剪计算 | 逐帧计算嘴部区域矩形，标准化为 128x128 | 几何计算 |
| 4. 3D 人脸模型生成 | 构建 OBJ 网格，计算逐帧变换矩阵 | 自定义网格生成、矩阵分解 |
| 5. 参考特征提取 | DINet_mini 前向传播，获取压缩参考特征 | PyTorch 推理 |
| 6. 打包输出 | 将所有数据合并为单个 gzip JSON 文件 | 每个角色约 2MB |

#### 视频要求

- **格式**：MP4
- **人脸**：单人、正面、鼻子位于两眼之间
- **分辨率**：至少 200x200 像素
- **时长**：至少 2 秒，推荐 10 秒到 2 分钟
- **内容**：面部清晰可见，头部转动幅度小，光线稳定

## 高级：从零训练模型

大多数用户不需要这一步。`dhy_human/checkpoint/` 中的预训练权重适用于任何人的脸。只有在需要自定义模型权重时才需要从零训练。

DINet_mini 和 LSTM 模型参照 [DH_live](https://github.com/kleinlee/DH_live) 的方法训练。训练脚本位于 `dhy_human/training/` 目录：

- `dhy_human/training/train/` — DINet 渲染模型训练
- `dhy_human/training/train_audio/` — LSTM 音频到表情模型训练

训练需要 CUDA 11.8+ 的 GPU。具体的数据准备和训练命令请参考对应目录中的脚本。

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **前端** | React 19、TypeScript 6、Vite 8 | UI 框架 |
| **人脸渲染** | WebGL 2 + 自定义着色器 | 实时 3D 网格变形目标动画 |
| **音频处理** | Emscripten/Qt WASM 模块 | 浏览器端从音频提取混合变形 |
| **训练服务器** | FastAPI、Uvicorn | REST API + SSE 进度流 |
| **人脸检测** | MediaPipe FaceMesh（478 个关键点） | 训练管道中的关键点提取 |
| **神经渲染** | DINet_mini（PyTorch） | 参考特征提取 |
| **语音后端** | .NET 9、WebSocket | ASR/LLM/TTS 编排 |
| **语音识别** | FunASR | 通过 WebSocket 进行语音转文本 |
| **大语言模型** | OpenAI 兼容 API（DeepSeek-V3） | 流式聊天补全 |
| **语音合成** | 火山引擎 / Coze / 语音克隆 | 多种 TTS 后端 |
| **容器化** | Docker | 多阶段 .NET 构建部署 |

## 项目结构

```
Realtime_human/
├── LICENSE
├── README.md                          # 英文文档
├── README_CN.md                       # 中文文档
├── .gitignore
│
├── dhy_human/                         # 数字人核心
│   ├── requirements.txt               # Python 依赖
│   ├── checkpoint/                    # 预训练模型权重
│   │   ├── DINet_mini/                # DINet 渲染模型
│   │   └── lstm/                      # LSTM 音频模型
│   ├── data/                          # 共享数据（PCA、人脸模板）
│   │
│   ├── living_human/                  # 运行时组件
│   │   ├── training_server/           # FastAPI 训练服务器
│   │   │   ├── server.py              # API 接口
│   │   │   ├── pipeline.py            # 6 步训练管道
│   │   │   ├── requirements.txt
│   │   │   └── static/                # 训练管理界面
│   │   │
│   │   ├── react-frontend/            # React + WebGL 前端
│   │   │   ├── src/
│   │   │   │   ├── components/        # UI 组件
│   │   │   │   ├── hooks/             # React Hooks
│   │   │   │   │   ├── useWasm.ts     # WASM 模块加载
│   │   │   │   │   ├── useWebGL.ts    # WebGL2 渲染器
│   │   │   │   │   ├── useRenderLoop.ts # 动画循环
│   │   │   │   │   ├── useWebSocket.ts # 语音服务器连接
│   │   │   │   │   ├── useAudio.ts    # TTS 音频播放
│   │   │   │   │   ├── useMicrophone.ts # 麦克风采集+重采样
│   │   │   │   │   └── useCharacter.ts # 角色管理
│   │   │   │   └── lib/               # WASM/WebGL 工具
│   │   │   └── public/
│   │   │       ├── mode/human.wasm    # 人脸处理 WASM
│   │   │       └── characters/        # 已部署的角色资源
│   │   │
│   │   └── video_data_disponse.py     # CLI 训练工具（旧版）
│   │
│   ├── talkingface/                   # 神经说话人脸模型
│   │   ├── models/
│   │   │   ├── DINet_mini.py          # 紧凑版 DINet 架构
│   │   │   ├── DINet.py               # 完整版 DINet 架构
│   │   │   └── audio2bs_lstm.py       # 音频到表情 LSTM
│   │   ├── render_model_mini.py       # DINet 推理封装
│   │   ├── run_utils.py               # 人脸矩阵计算
│   │   ├── mediapipe_utils.py         # MediaPipe 工具
│   │   └── utils.py                   # 共享常量和工具
│   │
│   ├── model/                         # 3D 人脸模型工具
│   │   └── obj/
│   │       ├── obj_utils.py           # OBJ 网格生成
│   │       └── wrap_utils.py          # 网格顶点包裹
│   │
│   └── training/                      # 模型训练脚本
│       ├── train/                     # DINet 渲染模型训练
│       └── train_audio/               # LSTM 音频模型训练
│
└── voice_server/                      # .NET 语音对话后端
    ├── HumanVoice_Backstage.csproj    # .NET 9 项目
    ├── HumanVoice_Backstage.sln
    ├── Dockerfile                     # 容器化部署
    ├── appsettings.Example.json       # 配置模板（已追踪）
    ├── appsettings.json               # 运行时配置（已忽略）
    ├── Program.cs                     # 入口文件
    ├── Config/AppConfig.cs            # 配置加载器
    ├── Communication/
    │   ├── SocketCommunication.cs     # WebSocket 服务器
    │   └── DisponseData/
    │       └── WebSocketClientDisponseData.cs  # ASR → LLM → TTS 管道
    ├── LLM/LLM.cs                     # LLM 客户端（流式）
    └── TTS/TTS.cs                     # TTS 客户端（多后端）
```

## 语音对话流程

```
  用户说话              浏览器采集音频
       │                        │
       │                        ▼
       │                 重采样至 16kHz
       │                 转换为 16-bit PCM
       │                        │
       │                        ▼
       │              WebSocket 发送至 voice_server
       │              (ws://hostname:19465)
       │                        │
       │                        ▼
       │                 转发至 FunASR
       │                        │
       │                        ▼
       │                 语音识别结果
       │                        │
       │                        ▼
       │                 发送文本至 LLM
       │                 （流式响应）
       │                        │
       │                        ▼
       │                 按中英文标点拆分
       │                 响应句子
       │                        │
       │                        ▼
       │                 每句 → TTS 语音合成
       │                        │
       │                        ▼
       │                 音频（base64）+ 文本
       │                 返回至浏览器
       │                        │
       ▼                        ▼
  聊天面板显示文本        音频通过 Web Audio API 播放
                         WASM 提取混合变形
                         WebGL 渲染口型同步人脸
```

## 配置说明

### 角色配置（`characters/index.json`）

每个角色条目支持以下字段：

```json
{
  "id": "assistant",
  "name": "我的助手",
  "preview": "characters/assistant/preview.jpg",
  "systemMessage": "你是一个有帮助的助手...",
  "voiceType": "BV700_streaming"
}
```

| 字段 | 说明 |
|------|------|
| `id` | 唯一标识符，需与角色目录名一致 |
| `name` | 角色选择器中的显示名称 |
| `preview` | 预览图片路径（jpg/svg） |
| `systemMessage` | LLM 系统提示词，定义角色的性格和行为 |
| `voiceType` | TTS 语音类型标识（如 `BV007_streaming`、`BV700_streaming`） |

### 语音服务器配置（`appsettings.json`）

完整配置模板请参考 [`voice_server/appsettings.Example.json`](voice_server/appsettings.Example.json)。

## API 参考

### 训练服务器（端口 8000）

| 方法 | 接口 | 说明 |
|------|------|------|
| `POST` | `/api/train` | 上传视频和名称，启动训练任务 |
| `GET` | `/api/tasks` | 列出所有训练任务 |
| `GET` | `/api/tasks/{id}` | 获取任务详情 |
| `GET` | `/api/tasks/{id}/progress` | SSE 实时进度流 |
| `GET` | `/api/download/{id}` | 下载生成的角色数据 |
| `POST` | `/api/deploy/{id}` | 将已完成的角色部署到前端 |
| `GET` | `/api/characters` | 列出已部署的角色 |
| `DELETE` | `/api/characters/{id}` | 删除已部署的角色 |
| `DELETE` | `/api/tasks/{id}` | 删除训练任务 |

### 语音服务器（WebSocket 端口 19465）

| 接口 | 协议 | 说明 |
|------|------|------|
| `/recognition` | WebSocket | 双向音频/文本通信 |

查询参数：
- `isSendConfig` — 连接时发送角色配置
- `isKeLong` — 使用语音克隆 TTS
- `isLLMVoice` — 启用 LLM 语音模式

## 部署

### Docker 部署（语音服务器）

```bash
cd voice_server
docker build -t realtime-human-voice .
docker run -d \
  -p 19465:19465 \
  -v $(pwd)/appsettings.json:/app/appsettings.json \
  realtime-human-voice
```

### 生产构建（前端）

```bash
cd dhy_human/living_human/react-frontend
npm run build
# 使用任意静态文件服务器托管 dist/ 目录
```

### 独立发布（语音服务器）

```bash
cd voice_server
dotnet publish -c Release -r linux-x64 --self-contained
# 将发布的目录部署到你的服务器
```

## 浏览器兼容性

| 浏览器 | 状态 | 备注 |
|--------|------|------|
| Chrome 90+ | 支持 | WebGL + WASM 性能最佳 |
| Edge 90+ | 支持 | 基于 Chromium，与 Chrome 一致 |
| Firefox 90+ | 支持 | 支持 WebGL 2 和 WASM |
| Safari 17+ | 部分支持 | 长视频需要 iOS 17+ |
| 移动端 Chrome | 支持 | 可在 Android 设备上运行 |
| 移动端 Safari | 部分支持 | 需要 iOS 17+ |

## 开发

### 前端开发

```bash
cd dhy_human/living_human/react-frontend
npm install
npm run dev          # 开发服务器 http://localhost:5173
npm run build        # 生产构建
npm run lint         # ESLint 检查
```

### 训练管道开发

```bash
conda activate realtime_human
cd dhy_human

# 使用单个视频测试
python living_human/video_data_disponse.py path/to/video.mp4
```

### 语音服务器开发

```bash
cd voice_server
dotnet run           # 启动并热重载
dotnet watch         # 监听文件变化
```

## 致谢

特别感谢 [@kleinlee](https://github.com/kleinlee) 的 [**DH_live**](https://github.com/kleinlee/DH_live) 项目，这是一个优秀的实时 2D 视频数字人开源项目。

## 许可证

本项目基于 [MIT 许可证](LICENSE) 开源。
