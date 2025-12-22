# app.py 完整修复版
from flask import Flask, redirect, url_for, current_app  # 确保导入 current_app
from flask_login import LoginManager, current_user, login_required
from models import db, User
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.student import student_bp
from routes.course import course_bp
from routes.skill import skill_bp
from routes.teacher import teacher_bp
import os
from datetime import datetime  # 用于文件命名和模型默认值

# 定义过滤器函数
def datetimeformat(value, format='%Y-%m-%d %H:%M'):
    """
    Jinja2 过滤器：将 datetime 对象格式化为指定字符串。
    如果输入是字符串 "now"，则返回当前时间。
    """
    if value == "now":
        dt = datetime.now()
    elif isinstance(value, datetime):
        dt = value
    else:
        # 尝试解析输入值，如果它不是 datetime 对象
        try:
            dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S') # 假设一个默认时间格式
        except:
            return value  # 如果解析失败，返回原始值

    return dt.strftime(format)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.jinja_env.filters['datetimeformat'] = datetimeformat

# -------------------------- 1. 文件上传配置 (新增) --------------------------
# 定义文件上传目录（确保 'static/uploads/certificates' 路径存在）
UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static/uploads/certificates')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx'}  # 允许的文件后缀

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['ALLOWED_EXTENSIONS'] = ALLOWED_EXTENSIONS

# 初始化数据库
db.init_app(app)

# 初始化登录管理器
login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'
login_manager.session_protection = 'strong'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# 注册蓝图（注意admin_bp带前缀/admin）
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp, url_prefix='/admin')  # 管理员路由前缀/admin
app.register_blueprint(student_bp)
app.register_blueprint(course_bp)
app.register_blueprint(skill_bp)
app.register_blueprint(teacher_bp)


@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    return redirect(url_for('auth.login'))


# -------------------------- 2. 文件上传辅助函数 (新增) --------------------------
# 辅助函数：检查文件类型（定义为全局函数，并在 app_context 中挂载）
def allowed_file(filename):
    """检查文件后缀是否在允许列表内"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


if __name__ == '__main__':
    with app.app_context():
        # 核心修复：统一导入generate_password_hash，所有分支都能使用
        from werkzeug.security import generate_password_hash

        db.create_all()

        # --- 文件系统初始化 (新增) ---
        # 确保上传文件夹存在
        if not os.path.exists(current_app.config['UPLOAD_FOLDER']):
            os.makedirs(current_app.config['UPLOAD_FOLDER'])

        # 将 allowed_file 函数挂载到 app 实例上，供路由中调用
        current_app.allowed_file = allowed_file


        # --- 通用初始化函数 ---
        # app.py 中的通用初始化函数 (已修复)
        def create_or_update_user(username, password, role):
            user = User.query.filter_by(username=username).first()

            needs_update = False

            if not user:
                # 1. 用户不存在：创建新用户
                user = User(
                    username=username,
                    role=role
                )
                db.session.add(user)
                needs_update = True
                print(f"✅ {['学生', '教师', '管理员'][role]}账号已创建：{username}/{password} (role={role})")

            if user.role != role:
                # 2. 角色不匹配：更新角色
                user.role = role
                needs_update = True

            # 3. ⚠️ 关键修复：强制设置/重置密码哈希
            # 无论用户是新建还是已存在，都调用 set_password 确保密码哈希是正确的
            user.set_password(password)
            needs_update = True

            if needs_update:
                db.session.commit()
                print(f"✅ 账号 {username} 的密码哈希和角色（如果需要）已更新。")
            else:
                print(f"✅ 账号 {username} 已存在（role={role}），无需更新。")


        # 1. 初始化/修正管理员账号（role=2）
        create_or_update_user('admin', 'admin123', 2)

        # 2. 初始化教师账号（role=1）
        create_or_update_user('teacher', 'teacher123', 1)

        # 3. 初始化学生账号（role=0）
        create_or_update_user('student', 'student123', 0)

    # 启动应用（debug=True仅开发环境用）
    app.run(debug=True, host='0.0.0.0', port=5000)