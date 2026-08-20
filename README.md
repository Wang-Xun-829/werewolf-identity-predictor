# 狼人杀身份预测程序

根据线下实时对局中观察到的玩家行为，通过贝叶斯推理实时预测各玩家身份。

## 功能

1. 录入玩家行为（发起者、目标、行为类型、身份、阵营、对局编号）
2. 基于贝叶斯算法实时预测各玩家身份概率
3. 对局结束后补全真实身份，系统自动对比并优化算法参数
4. 身份库、行为库、版型库的增删改管理

## 技术栈

- 后端：Python + Flask
- 前端：HTML + CSS + JavaScript
- 数据库：PostgreSQL (Neon)
- 部署：Render
- 代码托管：GitHub

## 本地运行

```bash
pip install -r requirements.txt
python app.py
```

访问 http://127.0.0.1:5000
