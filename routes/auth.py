from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, login_required, logout_user, current_user
# 确保导入了 db 和 User
from models import db, User
# 确保导入了密码处理工具
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import FlaskForm  # 假设登录也使用表单
from wtforms import StringField, PasswordField, SubmitField  # 导入新的字段类型
from wtforms.validators import DataRequired, Length  # 导入验证器

auth_bp = Blueprint('auth', __name__)


# -------------------------- 辅助表单 (已修复) --------------------------
class LoginForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(message='用户名不能为空'), Length(min=4)])
    password = PasswordField('密码', validators=[DataRequired(message='密码不能为空')])
    submit = SubmitField('登录')


# ----------------------------------------------------------------------


# routes/auth.py 中的 login 路由 (最终调试版)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # 实例化表单
    form = LoginForm()

    # 打印请求方法
    print(f"\n--- 收到请求方法: {request.method} ---")

    # 提交时，使用 form.validate_on_submit()
    if form.validate_on_submit():
        # ⚠️ 关键检查点 1：如果成功，打印数据
        username_data = form.username.data
        password_data = form.password.data
        print(f"Flask-WTF 验证成功。尝试登录: Username={username_data}")

        user = User.query.filter_by(username=username_data).first()

        # 修复：使用 user.password_hash 进行验证，并检查 user.password_hash 是否存在
        if user and user.password_hash and check_password_hash(user.password_hash, password_data):
            login_user(user)
            flash('登录成功！', 'success')
            return redirect(url_for('auth.dashboard'))  # 跳转到角色分发路由

        # 密码或用户不存在时，给 form 加上错误，或直接闪现消息
        flash('用户名或密码错误。', 'danger')
        print(">>> 密码验证失败或用户不存在 <<<")

    else:
        # ⚠️ 关键检查点 2：打印 form.validate_on_submit() 失败原因
        if request.method == 'POST':
            print("Flask-WTF 验证失败。请检查 CSRF 或字段验证错误。详细错误信息:")
            for field, errors in form.errors.items():
                print(f"  字段 {field} 错误: {', '.join(errors)}")

    # 修正模板路径为 'auth/login.html'，以符合蓝图惯例
    return render_template('auth/login.html', form=form)

# 注册（仅学生）
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))

    if request.method == 'POST':
        # 假设通过 request.form 获取数据
        username = request.form.get('username')
        password = request.form.get('password')

        # 基础验证
        if not username or not password:
            flash('用户名和密码不能为空！', 'warning')
            return redirect(url_for('auth.register'))

        if User.query.filter_by(username=username).first():
            flash('用户名已被占用！', 'warning')
            return redirect(url_for('auth.register'))

        new_user = User(
            username=username,
            role=0  # 学生
        )

        # 修复：使用 set_password 方法处理密码
        try:
            new_user.set_password(password)
        except AttributeError:
            flash('系统错误：User模型中缺少set_password方法，无法注册！', 'danger')
            return redirect(url_for('auth.register'))

        db.session.add(new_user)
        db.session.commit()

        flash('注册成功！请登录', 'success')
        return redirect(url_for('auth.login'))

    # 确保注册模板在 templates/auth/register.html
    return render_template('auth/register.html')


# 登出
@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('已成功登出！', 'success')
    return redirect(url_for('auth.login'))


# 核心修复：角色分发路由（避免循环）
@auth_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 0:
        # 学生
        return redirect(url_for('student.student_index'))
    elif current_user.role == 1:
        # 教师
        return redirect(url_for('teacher.teacher_index'))
    elif current_user.role == 2:
        # 管理员
        return redirect(url_for('admin.admin_index'))
    else:
        # 异常角色：直接登出
        logout_user()
        flash('角色异常，请重新登录！', 'danger')
        return redirect(url_for('auth.login'))


@auth_bp.route('/profile')
@login_required
def profile():
    """用户的个人资料页面"""

    # 假设 'profile.html' 模板存在于 templates/auth/ 目录下
    # 您可能需要在这里查询用户数据 (如 user.skills, user.selected_courses)

    # 渲染 profile.html，并传入当前用户对象
    return render_template('auth/profile.html', user=current_user)