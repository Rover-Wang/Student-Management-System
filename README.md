# 校园学业成长与技能追踪平台

## 项目简介

本项目是面向高校学生的轻量化学业管理系统，聚焦“学业规划+技能追踪”核心场景，支持课程管理、学习计划制定、技能成长记录、资源匹配等功能，基于Python Flask框架开发，采用SQLite数据库（无需额外安装，开箱即用），适配软件工程课程设计要求。

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
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

app = Flask(__name__)
# SQLite数据库路径配置（项目根目录下生成data.db文件）
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.root_path, 'data.db')
app.config['SECRET_KEY'] = 'your-secret-key-123456'  # 自定义密钥
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'
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

db = SQLAlchemy()

# 用户模型（学生/管理员）
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.SmallInteger, default=0)  # 0=学生，1=管理员
    create_time = db.Column(db.DateTime, default=datetime.now)

# 课程模型
class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    credit = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    create_time = db.Column(db.DateTime, default=datetime.now)
    # 关联用户
    user = db.relationship('User', backref=db.backref('courses', lazy=True))

# 学习计划模型
class StudyPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text)
    status = db.Column(db.SmallInteger, default=0)  # 0=未完成，1=已完成
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    create_time = db.Column(db.DateTime, default=datetime.now)
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

# 技能模型
class Skill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    current_level = db.Column(db.Integer, default=1)  # 1-5级
    target_level = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    create_time = db.Column(db.DateTime, default=datetime.now)
    user = db.relationship('User', backref=db.backref('skills', lazy=True))

# 技能记录模型
class SkillRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)  # 学习内容/证明描述
    hours = db.Column(db.Float, default=0)  # 学习时长（小时）
    skill_id = db.Column(db.Integer, db.ForeignKey('skill.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    create_time = db.Column(db.DateTime, default=datetime.now)
```

## 测试指南

### 1. 单元测试示例（tests/test_course.py）

```python
import unittest
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app, db
from models import Course, User

class CourseTestCase(unittest.TestCase):
    def setUp(self):
        """测试前置操作：使用内存SQLite数据库"""
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = app.test_client()
        
        with app.app_context():
            db.create_all()
            # 创建测试用户
            test_user = User(username='testuser', password='testpass')
            db.session.add(test_user)
            db.session.commit()

    def test_add_course(self):
        """测试添加课程接口"""
        response = self.client.post('/api/course/add', 
                                   json={'name': '软件工程', 'credit': 3.0, 'user_id': 1},
                                   content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['msg'], '课程添加成功')

    def test_get_course_list(self):
        """测试获取课程列表接口"""
        # 先添加测试数据
        with app.app_context():
            test_course = Course(name='计算机网络', credit=2.5, user_id=1)
            db.session.add(test_course)
            db.session.commit()
        
        # 调用接口
        response = self.client.get('/api/course/list?user_id=1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json['data']), 1)
        self.assertEqual(response.json['data'][0]['name'], '计算机网络')

    def tearDown(self):
        """测试后置操作：清理数据库"""
        with app.app_context():
            db.session.remove()
            db.drop_all()

if __name__ == '__main__':
    unittest.main()
```

### 2. 功能测试用例

| 测试ID | 测试功能       | 操作步骤                                                                 | 预期结果                                  |
|--------|----------------|--------------------------------------------------------------------------|-------------------------------------------|
| TC001  | 用户登录       | 访问<http://127.0.0.1:5000/login，输入用户名student1/密码123456，点击登录> | 登录成功，跳转学生首页                    |
| TC002  | 添加课程       | 登录后进入课程管理页，输入课程名和学分，点击添加                          | 提示添加成功，课程列表显示新增课程，data.db中生成记录 |
| TC003  | 生成雷达图     | 进入技能页添加Java（等级2）、Python（等级1），点击生成雷达图              | 页面显示技能雷达图                        |

### 3. 接口测试示例

#### 添加课程接口

- 请求方式：POST
- 请求URL：<http://127.0.0.1:5000/api/course/add>
- 请求体：{"name": "数据结构", "credit": 4.0, "user_id": 1}
- 响应：{"code": 200, "msg": "课程添加成功"}

## 项目结构

```
academic-growth-platform/
├── app.py               # 项目入口（Flask初始化、配置）
├── models.py            # 数据模型定义（SQLite）
├── data.db              # SQLite数据库文件（自动生成）
├── routes/              # 路由模块
│   ├── auth.py          # 用户认证（登录/注册）
│   ├── course.py        # 课程管理
│   ├── skill.py         # 技能追踪
│   └── admin.py         # 管理员功能
├── static/              # 静态资源（CSS/JS/ECharts）
├── templates/           # HTML模板
├── tests/               # 测试用例
│   ├── test_course.py
│   └── test_skill.py
└── README.md            # 项目说明
```

## 核心功能模块

1. **学业规划模块**  
   - 课程管理：添加/编辑/删除课程，关联用户  
   - 学习计划：制定计划、标记完成状态、进度统计  
   - 成绩分析：录入成绩、计算GPA、生成分析报告  

2. **技能追踪模块**  
   - 技能目标：设置技能类型、当前等级、目标等级  
   - 成长记录：添加学习记录、累计时长、更新技能等级  
   - 数据可视化：生成技能雷达图、成长趋势图  

3. **资源匹配模块**  
   - 资源下载：学生下载学习资源  
   - 积分兑换：完成任务获取积分兑换资源  

4. **系统管理模块**  
   - 用户权限：区分学生/管理员角色  
   - 数据统计：统计用户数据、技能分布  

## SQLite优势说明

1. 无需独立安装数据库服务，Python内置支持  
2. 数据库文件（data.db）可随项目直接打包，便于部署  
3. 适合小型项目和课程设计，操作简单，无需配置复杂权限  

## 开发者信息

- 开发者：XXX（学号：XXX）  
- 开发时间：XXXX年XX月-XXXX年XX月  
- 课程设计：软件工程课程设计项目  
