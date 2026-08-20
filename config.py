"""
配置文件
- 本地开发时，从 .env 文件读取数据库地址
- 线上部署时，从 Render 的环境变量读取
"""
import os
from dotenv import load_dotenv

# 加载 .env 文件（仅本地开发用，线上由 Render 注入）
load_dotenv()

class Config:
    # 数据库连接地址
    # 本地开发时在 .env 里写 DATABASE_URL=postgresql://...
    # 线上 Render 会自动设置这个环境变量
    DATABASE_URL = os.getenv("DATABASE_URL", "")

    # Flask 密钥（用于 session，后续登录功能会用到）
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

    # 调试模式
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
