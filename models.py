from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask import flash

db = SQLAlchemy()


# -------------------------- 核心关联模型 (选课/成绩) --------------------------
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

    # 关系属性 (backref 会自动在 User 和 Course 中创建 'enrollments' 列表)
    student = db.relationship('User', backref=db.backref('enrollments', lazy='dynamic', cascade="all, delete-orphan"))
    course = db.relationship('Course', backref=db.backref('enrollments', lazy='dynamic', cascade="all, delete-orphan"))

    @property
    def grade_point(self):
        """修复绩点计算规则：按“60分=1.0，每增加1分+0.1”计算（示例：96分=4.6）"""
        if self.score is None:
            return 0.0
        if self.score < 60:
            return 0.0
        # 核心修正：60分对应1.0，每增加1分，绩点+0.1
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

    # 💡 辅助属性：为了兼容旧代码，方便直接获取课程列表
    @property
    def selected_courses(self):
        """返回该学生所有已选的课程对象列表"""
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

    # 注意：students 属性现在通过 Enrollment 的 backref 隐式访问略有不同
    # 如果需要直接访问所有学生对象，可以使用以下属性：
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
    is_public = db.Column(db.Boolean, default=False)  # 新增：是否公共技能
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


# models.py 中新增 Grade 模型
class Grade(db.Model):
    __tablename__ = 'grade'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    score = db.Column(db.Float)  # 成绩（0-100）
    create_time = db.Column(db.DateTime, default=datetime.now)
    update_time = db.Column(db.DateTime, onupdate=datetime.now)

    # 关联关系（可选）
    student = db.relationship('User', backref='grades')
    course = db.relationship('Course', backref='grades')