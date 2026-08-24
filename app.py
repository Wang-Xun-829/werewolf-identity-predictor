"""
狼人杀身份预测程序 - 主入口
"""
from flask import Flask, jsonify, render_template
from flask_cors import CORS
from config import Config
from db import init_db, seed_initial_data, get_db, DB_TYPE
from api import api as api_blueprint

app = Flask(__name__)
app.config.from_object(Config)

# 允许跨域请求
CORS(app)

# 注册 API 路由（所有接口都在 /api 前缀下）
app.register_blueprint(api_blueprint)


# ============================================================
# 全局错误处理器（确保API异常返回JSON，而不是HTML错误页）
# ============================================================
@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    error_detail = traceback.format_exc()
    print(f"[全局异常] {error_detail}")
    # 如果是API请求，返回JSON
    from flask import request
    if request.path.startswith('/api/'):
        return jsonify({
            "success": False,
            "message": f"服务器错误: {str(e)}",
            "error_type": type(e).__name__
        }), 500
    # 其他请求返回默认错误页
    return e


# ============================================================
# 页面路由
# ============================================================
@app.route("/")
def page_index():
    """首页 - 对局列表"""
    return render_template("index.html", active_page="home")


@app.route("/players")
def page_players():
    """玩家管理页"""
    return render_template("players.html", active_page="players")


@app.route("/admin")
def page_admin():
    """库管理页"""
    return render_template("admin.html", active_page="admin")


@app.route("/game/<int:game_id>")
def page_game(game_id):
    """对局详情页"""
    return render_template("game.html", active_page="home", game_id=game_id)


# ============================================================
# 系统接口
# ============================================================
@app.route("/health")
def health():
    """健康检查接口"""
    return jsonify({"status": "ok"})


@app.route("/init_db")
def init_database():
    """初始化数据库：创建所有表并插入默认身份/行为/版型数据"""
    try:
        init_db()
        seed_initial_data()
        return jsonify({
            "success": True,
            "message": "数据库初始化成功，已创建所有表并插入默认数据"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"数据库初始化失败: {str(e)}"
        }), 500


@app.route("/api_info")
def api_info():
    """API 信息页（JSON）"""
    db_status = "未初始化"
    role_count = 0
    action_count = 0
    game_count = 0
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM roles")
        role_count = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) as cnt FROM actions")
        action_count = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) as cnt FROM games")
        game_count = cur.fetchone()["cnt"]
        conn.close()
        if role_count > 0:
            db_status = "已初始化"
    except Exception as e:
        db_status = f"连接失败: {str(e)[:50]}"

    return jsonify({
        "app": "狼人杀身份预测程序",
        "version": "0.5.0",
        "database": {
            "type": DB_TYPE,
            "status": db_status,
            "roles_count": role_count,
            "actions_count": action_count,
            "games_count": game_count
        },
        "pages": {
            "首页": "/",
            "玩家管理": "/players",
            "库管理": "/admin",
            "对局详情": "/game/<id>"
        },
        "init_db": "/init_db"
    })


if __name__ == "__main__":
    # 本地运行：python app.py
    # 访问 http://127.0.0.1:5000 打开首页
    # 首次运行先访问 http://127.0.0.1:5000/init_db 初始化数据库
    app.run(host="0.0.0.0", port=5000, debug=app.config["DEBUG"])
