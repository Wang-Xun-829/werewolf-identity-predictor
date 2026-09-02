# 狼人杀身份预测系统 v5.0

一个基于贝叶斯推理和梯度下降学习的狼人杀身份预测系统，支持线下实时对局的玩家行为录入、身份实时预测、算法自学习优化。

## 技术栈

- **后端**: FastAPI + SQLAlchemy ORM
- **数据库**: PostgreSQL (Neon) / SQLite (开发)
- **前端**: 原生HTML/CSS/JavaScript (前后端分离)
- **部署**: Render + GitHub
- **算法**: 贝叶斯推理 + 梯度下降迭代学习

## 功能特性

### 核心功能
- ✅ 玩家行为实时录入（支持多选、多级行为分类）
- ✅ 基于贝叶斯算法的身份实时预测
- ✅ 对局结束后的算法自学习优化（梯度下降）
- ✅ 玩家个性化行为权重统计
- ✅ 预言家查验链推导分析
- ✅ 狼坑分析与约束管理
- ✅ 多情景假设推理
- ✅ 确认身份（逻辑基点）管理

### 游戏流程
- ✅ 完整的游戏阶段流转（上警→警上发言→警徽投票→死讯公布→白天发言→放逐投票→遗言）
- ✅ 玩家状态管理（上警/退水/存活/死亡）
- ✅ 投票权自动过滤
- ✅ 投票结果自动计算
- ✅ 狼人自爆处理

### 数据管理
- ✅ 身份库管理（增删改）
- ✅ 行为库管理（支持任意层级父子行为）
- ✅ 版型库管理（身份数量配置）
- ✅ 玩家库管理（支持拼音搜索）

### 界面体验
- ✅ 科技感深色主题UI
- ✅ 手机端响应式布局
- ✅ 预测结果抽屉式显示
- ✅ 行为搜索（支持拼音/拼音首字母/汉字）

## 项目结构

```
werewolf_v5/
├── backend/                    # 后端代码
│   ├── main.py                # FastAPI主程序
│   ├── database.py            # 数据库连接
│   ├── models.py              # SQLAlchemy数据模型
│   ├── schemas.py             # Pydantic模型
│   ├── inference.py           # 贝叶斯推理引擎
│   ├── result_status.py       # 行为结果状态推断
│   ├── prophet_inference.py   # 预言家查验链分析
│   ├── wolf_pit.py            # 狼坑分析
│   ├── game_flow.py           # 游戏流程管理
│   ├── gradient_learning.py   # 梯度下降学习
│   └── requirements.txt       # Python依赖
├── frontend/                   # 前端代码
│   ├── index.html             # 主页面
│   ├── css/
│   │   └── style.css          # 样式文件
│   └── js/
│       ├── api.js             # API调用封装
│       ├── common.js          # 通用功能
│       └── game.js            # 对局页面逻辑
├── migrate_data.py            # 数据迁移脚本
├── render.yaml                # Render部署配置
├── .env.example               # 环境变量示例
├── .gitignore                 # Git忽略文件
└── README.md                  # 项目说明
```

## 安装和运行

### 1. 克隆项目
```bash
git clone https://github.com/Wang-Xun-829/werewolf-identity-predictor.git
cd werewolf_v5
```

### 2. 安装依赖
```bash
cd backend
pip install -r requirements.txt
```

### 3. 配置环境变量
```bash
cp .env.example .env
# 编辑.env文件，设置DATABASE_URL
```

### 4. 运行开发服务器
```bash
cd backend
uvicorn main:app --reload
```

访问 http://localhost:8000 查看应用
访问 http://localhost:8000/docs 查看API文档

## 数据迁移

从werewolf_2迁移数据到werewolf_v5：

```bash
# 设置源数据库连接
export SOURCE_DB_URL="postgresql://user:password@host:port/source_db"

# 设置目标数据库连接
export DATABASE_URL="postgresql://user:password@host:port/target_db"

# 运行迁移脚本
python migrate_data.py
```

## 部署到Render

### 1. 推送到GitHub
```bash
git init
git add .
git commit -m "Initial commit: werewolf_v5"
git remote add origin https://github.com/Wang-Xun-829/werewolf-identity-predictor.git
git push -u origin main
```

### 2. 在Render创建服务
1. 登录Render控制台
2. 点击"New" → "Web Service"
3. 连接GitHub仓库
4. 配置：
   - Build Command: `cd backend && pip install -r requirements.txt`
   - Start Command: `cd backend && gunicorn main:app -w 1 -k uvicorn.workers.UvicornWorker`
5. 添加环境变量 `DATABASE_URL`（Neon数据库连接串）
6. 点击"Create Web Service"

## 算法说明

### 贝叶斯推理
- 先验概率：从版型配置动态计算
- 似然度：基于玩家行为权重和个性化系数
- 后验概率：贝叶斯公式计算
- 版型身份过滤：只预测当前版型包含的身份

### 梯度下降学习
- 触发时机：对局确认后自动触发
- 学习率：自适应（开始大，后来小）
- 最大迭代次数：3次
- 评估指标：综合得分（身份预测+阵营预测）
- 回滚机制：如果成绩下降，自动回滚到上一版本

## 数据库表结构

共20张表：
1. `factions` - 阵营表
2. `identities` - 身份表
3. `setups` - 版型表
4. `setup_identities` - 版型身份配置表
5. `action_types` - 行为类型表（支持多级分类）
6. `action_type_weights` - 行为默认权重表
7. `players` - 玩家表
8. `games` - 对局表
9. `game_players` - 对局玩家表
10. `actions` - 行为记录表
11. `identity_weights` - 玩家个性化权重表
12. `player_statuses` - 玩家状态表
13. `wolf_pit_constraints` - 狼坑约束表
14. `scenarios` - 情景假设表
15. `scenario_assignments` - 情景身份分配表
16. `confirmed_identities` - 确认身份表
17. `learning_logs` - 学习日志表
18. `weight_backups` - 权重备份表
19. `predictions` - 预测结果表
20. `prediction_scores` - 预测打分明细表

## 版本历史

- **v5.0** (2026-09-01): 全新重构，融合werewolf_2和werewolf_4优点，FastAPI+SQLAlchemy架构
- **v4.0**: werewolf_4版本，FastAPI+前后端分离
- **v2.0**: werewolf_2版本，Flask+服务端渲染，已上线运行

## 许可证

MIT License
