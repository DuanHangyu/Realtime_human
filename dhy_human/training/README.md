# Training

训练代码，用于训练 DINet 渲染模型和 LSTM 音频模型。

## 目录结构

```
training/
├── train/          # DINet 渲染模型训练
│   ├── data_preparation_face.py          # 人脸数据准备
│   ├── train_render_model.py             # 渲染模型训练脚本
│   ├── train_input_validation_render_model.py  # 输入验证训练
│   └── README.md
├── train_audio/    # LSTM 音频模型训练
│   ├── audio.py                          # 音频处理工具
│   ├── hparams.py                        # 超参数配置
│   ├── preparation_step0.py              # 数据准备步骤0（wav2lip 特征提取）
│   ├── preparation_step1.py              # 数据准备步骤1（PCA 降维）
│   ├── train_lstm.py                     # LSTM 训练脚本
│   ├── test.py                           # 测试脚本
│   └── models/                           # wav2lip 相关模型定义
└── model/          # 训练专用的模型代码
    ├── train.py                          # DINet_mini 训练脚本
    └── train_input_validation.py         # 输入验证训练
```

## 前置条件

训练脚本需要以下目录位于项目根目录（`dhy_human/`）：

- `talkingface/` — 共享模型和工具库
- `model/` — 共享 3D 模型工具
- `data/` — 共享数据文件（PCA 模型、人脸关键点均值）
- `checkpoint/` — 预训练权重

## 运行方式

所有训练脚本会自动将项目根目录加入 `sys.path`，可从项目根目录运行：

```bash
# DINet 渲染模型训练
python training/train/train_render_model.py

# LSTM 音频模型训练
python training/train_audio/train_lstm.py
```

## 训练流程

### DINet 渲染模型

1. `data_preparation_face.py` — 准备训练数据（人脸裁剪、关键点提取）
2. `train_render_model.py` — 训练 DINet 渲染模型
3. 训练完成后，权重保存到 `checkpoint/DINet_mini/`

### LSTM 音频模型

1. `preparation_step0.py` — 使用 wav2lip 提取音频特征
2. `preparation_step1.py` — PCA 降维处理
3. `train_lstm.py` — 训练 LSTM 模型
4. 训练完成后，权重保存到 `checkpoint/lstm/`
