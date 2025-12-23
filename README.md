# 学生学业管理系统

## 项目简介

本项目是面向高校学生的轻量化学业管理系统，聚焦“学业规划+技能追踪”核心场景，支持课程管理、学习计划制定、技能成长记录、资源匹配等功能，基于Python Flask框架开发，采用SQLite数据库（无需额外安装）。

## 技术栈

### 后端

- 核心框架：Flask 2.3.3
- 数据库ORM：SQLAlchemy 2.0.23
- 用户认证：Flask-Login 0.6.3
- 数据处理：Pandas 2.1.4

### 前端

- 基础技术：HTML5 + CSS3 + JavaScript
- UI框架：Bootstrap 5.3.2
- 数据可视化：ECharts 5.4.3

### 数据库

- 数据库：SQLite 3（内置数据库，无需独立部署）

### 开发工具

- Python 3.9+
- VS Code
- Postman（接口测试）

## 环境配置

### 1. 本地环境准备

- 安装Python 3.9+：<https://www.python.org/downloads/>

### 2. 项目依赖安装

```bash
# 创建虚拟环境
python -m venv venv

# Windows激活虚拟环境
venv\Scripts\activate

# macOS/Linux激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install Flask==2.3.3 Flask-SQLAlchemy==3.1.1 Flask-Login==0.6.3 pandas==2.1.4 numpy==1.26.0
```

### 3. 数据库配置（SQLite无需额外配置）

#### 修改项目配置（app.py）

```python
from flask import Flask, redirect, url_for, current_app
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

        try:
            dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
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

UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static/uploads/certificates')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx'}

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


def allowed_file(filename):
    """检查文件后缀是否在允许列表内"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


if __name__ == '__main__':
    with app.app_context():
        from werkzeug.security import generate_password_hash

        db.create_all()

        if not os.path.exists(current_app.config['UPLOAD_FOLDER']):
            os.makedirs(current_app.config['UPLOAD_FOLDER'])

        # 将 allowed_file 函数挂载到 app 实例上，供路由中调用
        current_app.allowed_file = allowed_file


        # 通用初始化函数
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
```

#### 初始化数据库表

```bash
# 进入Python交互环境
python
>>> from app import app, db
>>> with app.app_context():
...     db.create_all()  # 自动在项目根目录生成data.db文件
...     exit()
```

### 4. 启动项目

```bash
python app.py
```

访问地址：<http://127.0.0.1:5000>

## 数据模型设计（models.py）

```python
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask import flash

db = SQLAlchemy()


# 使用关联对象模式，代替简单的多对多表，以便存储成绩
class Enrollment(db.Model):
    __tablename__ = 'enrollment'

    id = db.Column(db.Integer, primary_key=True)
    # 外键
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)

    # 业务字段
    score = db.Column(db.Float, nullable=True)  # 成绩，允许为空(未录入)
    grade_point = db.Column(db.Float, nullable=True)  # 绩点（允许为空）
    create_time = db.Column(db.DateTime, default=datetime.now)  # 选课时间

    # 关系属性
    student = db.relationship('User', backref=db.backref('enrollments', lazy='dynamic', cascade="all, delete-orphan"))
    course = db.relationship('Course', backref=db.backref('enrollments', lazy='dynamic', cascade="all, delete-orphan"))

    @property
    def grade_point(self):
        if self.score is None:
            return 0.0
        if self.score < 60:
            return 0.0
        return 1.0 + (self.score - 60) * 0.1


# -------------------------- 核心用户/角色模型 --------------------------

class User(UserMixin, db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    role = db.Column(db.SmallInteger, default=0)  # 0=学生, 1=教师, 2=管理员
    create_time = db.Column(db.DateTime, default=datetime.now)
    password_hash = db.Column(db.String(128))

    # 关联定义
    teacher_info = db.relationship('Teacher', backref='user', uselist=False, lazy=True, cascade="all, delete-orphan")

    @property
    def selected_courses(self):
        return [enrollment.course for enrollment in self.enrollments]

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)


class Teacher(db.Model):
    __tablename__ = 'teacher'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    research_direction = db.Column(db.String(255), default='暂无')


# -------------------------- 业务数据模型 --------------------------

class Course(db.Model):
    __tablename__ = 'course'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    credit = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)

    # 课程创建者/授课教师 ID
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    create_time = db.Column(db.DateTime, default=datetime.now)

    # 关系
    teacher = db.relationship('User', backref=db.backref('taught_courses', lazy=True), foreign_keys=[teacher_id])

    @property
    def students(self):
        return [e.student for e in self.enrollments]


class Skill(db.Model):
    __tablename__ = 'skill'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    current_level = db.Column(db.Integer, default=1)  # 1-5
    target_level = db.Column(db.Integer, default=1)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    is_public = db.Column(db.Boolean, default=False)
    create_time = db.Column(db.DateTime, default=datetime.now)

class SkillRecord(db.Model):
    __tablename__ = 'skill_record'

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    hours = db.Column(db.Float, default=0)
    skill_id = db.Column(db.Integer, db.ForeignKey('skill.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    create_time = db.Column(db.DateTime, default=datetime.now)

    skill = db.relationship('Skill', backref=db.backref('records', lazy=True, cascade="all, delete-orphan"))


class StudyPlan(db.Model):
    __tablename__ = 'study_plan'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text)
    deadline = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.SmallInteger, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    create_time = db.Column(db.DateTime, default=datetime.now)

    user = db.relationship('User', backref=db.backref('plans', lazy=True, cascade="all, delete-orphan"))


class Feedback(db.Model):
    __tablename__ = 'feedback'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    create_time = db.Column(db.DateTime, default=datetime.now)
    status = db.Column(db.Integer, default=0)


class Certificate(db.Model):
    __tablename__ = 'certificate'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    description = db.Column(db.String(255))
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    upload_time = db.Column(db.DateTime, default=datetime.utcnow)

    # 审核字段
    status = db.Column(db.Integer, default=0, nullable=False)  # 0=待审核, 1=已通过, 2=未通过
    reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    review_time = db.Column(db.DateTime, nullable=True)
    review_notes = db.Column(db.Text, nullable=True)

    # 关系定义
    user = db.relationship('User', foreign_keys=[user_id],
                           backref=db.backref('certificates', lazy=True, cascade="all, delete-orphan"))
    reviewer = db.relationship('User', foreign_keys=[reviewer_id],
                               backref=db.backref('reviewed_certificates', lazy=True))

    __table_args__ = {'extend_existing': True}


class Notification(db.Model):
    __tablename__ = 'notification'

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_notifications', lazy=True)
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_notifications', lazy=True)

    __table_args__ = {'extend_existing': True}


class SystemLog(db.Model):
    __tablename__ = 'system_log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # 操作者ID
    action = db.Column(db.String(255), nullable=False)  # 操作内容描述
    ip_address = db.Column(db.String(50))  # 操作者IP
    create_time = db.Column(db.DateTime, default=datetime.now)  # 操作时间

    # 关联用户模型
    user = db.relationship('User', backref=db.backref('logs', lazy=True))


class Grade(db.Model):
    __tablename__ = 'grade'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    score = db.Column(db.Float)  # 成绩（0-100）
    create_time = db.Column(db.DateTime, default=datetime.now)
    update_time = db.Column(db.DateTime, onupdate=datetime.now)

    student = db.relationship('User', backref='grades')
    course = db.relationship('Course', backref='grades')
```

## 测试指南

### 1. 功能测试用例

| 测试ID | 测试功能       | 操作步骤                                                                 | 预期结果                                  |
|--------|----------------|--------------------------------------------------------------------------|-------------------------------------------|
| TC001  | 用户登录       | 访问<http://127.0.0.1:5000/login，输入用户名student/密码student123，点击登录> | 登录成功，跳转学生首页                    |
| TC002  | 添加课程       | 登录后进入课程管理页，输入课程名和学分，点击添加                          | 提示添加成功，课程列表显示新增课程，data.db中生成记录 |
| TC003  | 生成雷达图     | 进入技能页添加Java（等级2）、Python（等级1），点击生成雷达图              | 页面显示技能雷达图                        |

### 2. 接口测试示例

#### 添加课程接口

- 请求方式：POST
- 请求URL：<http://127.0.0.1:5000/api/course/add>
- 请求体：{"name": "数据结构", "credit": 4.0, "user_id": 1}
- 响应：{"code": 200, "msg": "课程添加成功"}

## 项目结构

```
软件工程/
├── .idea
├── __pycache__
├── instance
│   └── data.db
├── platform—venv
├── routes
│   ├── __pycache__
│   ├── __init__.py
│   ├── admin.py
│   ├── auth.py
│   ├── course.py
│   ├── skill.py
│   ├── student.py
│   └── teacher.py
├── static
│   ├── css
│   │   ├── main.css
│   │   └── student_style.css
│   ├── images
│   │   └── 1.png
│   ├── js
│   │   └── echarts.min.js
│   └── uploads
│       └── certificates
├── templates
│   ├── admin
│   ├── auth
│   ├── mailbox
│   ├── student
│   ├── teacher
│   └── base.html
├── app.py
├── models.py
├── README.md
└── requirements.txt
```

## 核心功能模块

1. **学业规划模块**  
   - 课程管理：添加/编辑/删除课程，关联用户  
   - 学习计划：制定计划、标记完成状态、进度统计  
   - 成绩分析：录入成绩、计算GPA  

2. **技能追踪模块**  
   - 技能目标：设置技能类型、当前等级、目标等级  
   - 成长记录：更新技能等级   

4. **系统管理模块**  
   - 用户权限：区分学生/教师/管理员角色  
   - 数据统计：统计用户数据、技能分布  

## SQLite优势说明

1. 无需独立安装数据库服务，Python内置支持  
2. 数据库文件（data.db）可随项目直接打包，便于部署  

## 开发者信息

- 开发者：王若凡  
- 开发时间：2025年10月-2025年12月  
- 课程设计：软件工程课程设计项目  

