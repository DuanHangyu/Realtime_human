# Living Human — 运行时

角色制作管道和前端界面，可独立于训练代码运行。

## 目录结构

```
living_human/
├── training_server/     # 角色制作服务器（FastAPI）
│   ├── server.py        # 服务器入口
│   ├── pipeline.py      # 训练管道逻辑
│   ├── requirements.txt # Python 依赖
│   └── static/          # Web 界面
│       └── index.html
├── react-frontend/      # React 前端（数字人交互界面）
├── video_data/          # 训练产出目录（角色数据）
└── video_data_disponse.py  # CLI 管道脚本（备用）
```

## 前置条件

运行时依赖以下目录位于项目根目录（`dhy_human/`）：

- `talkingface/` — 共享模型和工具库
- `model/` — 3D 模型工具（obj/、fusion mask）
- `data/` — 共享数据文件（PCA 模型、人脸关键点均值）
- `checkpoint/` — 预训练权重（DINet_mini、LSTM）

## 使用方式

### 方式一：Web 服务器（推荐）

```bash
cd living_human/training_server
pip install -r requirements.txt
python server.py
```

打开浏览器访问 http://localhost:8000，上传视频即可自动完成角色制作。

### 方式二：CLI 脚本

```bash
cd living_human
python video_data_disponse.py <视频文件> <输出目录>
```

### 前端开发

```bash
cd living_human/react-frontend
npm install
npm run dev
```

访问 http://localhost:5173，查看数字人交互界面。

## 部署流程

1. 通过训练服务器上传视频，完成角色制作
2. 在训练服务器界面点击"部署"按钮
3. 角色文件自动复制到 `react-frontend/public/characters/`
4. 前端界面自动识别新角色
