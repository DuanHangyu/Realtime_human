# Living Human — 2D 数字人

基于 DINet + LSTM 的 2D 数字人系统，支持从视频训练定制角色并实时交互。

## 项目结构

```
dhy_human/
├── training/                # 训练代码（独立部分）
│   ├── train/               # DINet 渲染模型训练
│   ├── train_audio/         # LSTM 音频模型训练
│   └── model/               # 训练专用模型代码
├── living_human/            # 运行时（角色制作 + 前端）
│   ├── training_server/     # FastAPI 角色制作服务器
│   ├── react-frontend/      # React 数字人交互前端
│   ├── video_data/          # 角色产出数据
│   └── video_data_disponse.py  # CLI 管道脚本
├── talkingface/             # 共享：模型定义与工具库
├── model/                   # 共享：3D 模型工具（obj/、fusion mask）
├── data/                    # 共享：PCA 模型、人脸关键点数据
├── checkpoint/              # 预训练权重
└── requirements.txt         # Python 依赖
```

## 快速开始

### 运行角色制作服务器

```bash
cd living_human/training_server
pip install -r requirements.txt
python server.py
```

访问 http://localhost:8000

### 运行前端

```bash
cd living_human/react-frontend
npm install
npm run dev
```

访问 http://localhost:5173

### 训练新模型

```bash
# DINet 渲染模型
python training/train/train_render_model.py

# LSTM 音频模型
python training/train_audio/train_lstm.py
```

详见 [training/README.md](training/README.md)。

## 架构说明

- **训练代码**（`training/`）和**运行时代码**（`living_human/`）完全分离
- 唯一的桥梁是 `checkpoint/` 中的预训练权重
- `talkingface/`、`model/obj/`、`data/` 是共享模块，被双方使用
- 运行时**不依赖**训练代码，可以独立部署
