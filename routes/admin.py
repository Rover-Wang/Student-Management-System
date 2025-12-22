from flask import Blueprint, render_template, jsonify, flash, redirect, url_for, request, current_app
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from functools import wraps
# 导入所需的字段和验证器
from wtforms import StringField, IntegerField, SubmitField, SelectField, FloatField, PasswordField
from wtforms.validators import DataRequired, Length, NumberRange, EqualTo, ValidationError
from models import db, User, Course, Skill, Teacher, Certificate, Notification, SystemLog  # 移除 student_course 导入
from collections import defaultdict
from datetime import datetime
import os

# 全局蓝图定义
admin_bp = Blueprint('admin', __name__)


# --- 辅助函数：记录系统日志 ---
def log_operation(action_desc):
    """
    记录管理员操作日志
    :param action_desc: 操作描述，例如 "删除了用户 ID:5"
    """
    if current_user.is_authenticated:
        try:
            # 获取真实IP (如果有代理的情况)
            ip = request.headers.get('X-Forwarded-For', request.remote_addr)

            new_log = SystemLog(
                user_id=current_user.id,
                action=action_desc,
                ip_address=ip,
                create_time=datetime.now()  # 补充日志创建时间
            )
            db.session.add(new_log)
            # 注意：这里不需要单独 commit，通常跟随业务逻辑一起 commit
        except Exception as e:
            print(f"日志记录失败: {e}")


# --- 辅助函数：角色权限装饰器 ---
def role_required(required_role):
    """
    检查当前用户是否具有所需的角色权限。
    role=0: 学生, role=1: 教师, role=2: 管理员
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('请先登录以访问此页面。', 'warning')
                return redirect(url_for('auth.login'))

            if current_user.role < required_role:
                flash('权限不足，无法访问此页面。', 'danger')
                return redirect(url_for('auth.dashboard'))

            return f(*args, **kwargs)

        return decorated_function

    return decorator


# -------------------------- 表单类定义 --------------------------
class UserForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(), Length(min=4, max=50)])
    password = PasswordField('密码', validators=[
        DataRequired(),
        Length(min=6),
        EqualTo('confirm_password', message='两次输入的密码必须匹配')
    ])
    confirm_password = PasswordField('确认密码', validators=[DataRequired()])
    role = SelectField('用户角色',
                       choices=[('0', '学生'), ('1', '教师'), ('2', '管理员')],
                       coerce=int,
                       default=0)
    submit = SubmitField('保存用户')

    def validate_username(self, field):
        # 新增用户时校验用户名唯一性，编辑时跳过自身
        user_id = request.args.get('user_id', 0, type=int)
        existing_user = User.query.filter_by(username=field.data).first()
        if existing_user and existing_user.id != user_id:
            raise ValidationError('该用户名已存在。')


class CourseForm(FlaskForm):
    name = StringField('课程名称', validators=[DataRequired(message='课程名称不能为空')])
    credit = FloatField('学分', validators=[
        DataRequired(message='学分不能为空'),
        NumberRange(min=0.5, max=10, message='学分需在0.5-10之间')
    ])
    submit = SubmitField('添加课程')


# 专门给管理员用的简化技能表单 (无等级)
class AdminSkillForm(FlaskForm):
    name = StringField('技能名称', validators=[DataRequired(), Length(min=2, max=50)])
    submit = SubmitField('添加技能')


class SkillForm(FlaskForm):
    name = StringField('技能名称', validators=[DataRequired(), Length(min=2, max=50)])
    current_level = SelectField('当前等级',
                                choices=[(1, '入门'), (2, '基础'), (3, '熟练'), (4, '精通'), (5, '专家')],
                                coerce=int,
                                validators=[DataRequired()])
    target_level = SelectField('目标等级',
                               choices=[(1, '入门'), (2, '基础'), (3, '熟练'), (4, '精通'), (5, '专家')],
                               coerce=int,
                               validators=[DataRequired()])
    submit = SubmitField('添加技能')


# -------------------------- 管理员路由 --------------------------

@admin_bp.route('/index')
@login_required
def admin_index():
    if current_user.role != 2:
        flash('无管理员权限！', 'danger')
        return redirect(url_for('auth.dashboard'))

    students = User.query.filter_by(role=0).all()
    courses = Course.query.all()
    skills = Skill.query.all()

    total_students = len(students)
    total_courses = len(courses)
    total_skills = len(skills)

    student_time_stats = defaultdict(int)
    for student in students:
        if hasattr(student, 'create_time') and student.create_time:
            time_key = student.create_time.strftime('%Y-%m')
            student_time_stats[time_key] += 1

    sorted_time_stats = sorted(student_time_stats.items())
    time_labels = [item[0] for item in sorted_time_stats]
    time_data = [item[1] for item in sorted_time_stats]

    return render_template('admin/index.html',
                           students=students,
                           courses=courses,
                           skills=skills,
                           total_students=total_students,
                           total_courses=total_courses,
                           total_skills=total_skills,
                           time_labels=time_labels,
                           time_data=time_data)


@admin_bp.route('/api/get_students')
@login_required
def get_students():
    if current_user.role != 2:
        return jsonify({'code': 403, 'msg': '无权限访问！'})

    students = User.query.filter_by(role=0).all()
    student_data = [{
        'id': student.id,
        'username': student.username,
        'create_time': student.create_time.strftime('%Y-%m-%d') if hasattr(student,
                                                                           'create_time') and student.create_time else '-',
        'course_count': len(student.selected_courses) if hasattr(student, 'selected_courses') else 0,
        'skill_count': len(student.skills) if hasattr(student, 'skills') else 0
    } for student in students]

    return jsonify({'code': 200, 'data': student_data})


@admin_bp.route('/course/add', methods=['GET', 'POST'])
@login_required
def add_course():
    if current_user.role < 1:
        flash('无权限添加课程，只有教师或管理员可以操作。', 'danger')
        return redirect(url_for('auth.dashboard'))

    form = CourseForm()
    if form.validate_on_submit():
        new_course = Course(
            name=form.name.data,
            credit=form.credit.data,
            teacher_id=current_user.id,
            create_time=datetime.now()  # 补充创建时间
        )
        db.session.add(new_course)

        # ✅ [日志]
        log_operation(f"添加了课程: {new_course.name} (学分: {new_course.credit})")

        db.session.commit()
        flash('课程添加成功', 'success')

        if current_user.role == 2:
            return redirect(url_for('admin.admin_index'))
        else:
            return redirect(url_for('teacher.course_manage'))

    return render_template('admin/add_course.html', form=form)


@admin_bp.route('/user/add', methods=['GET', 'POST'])
@login_required
def add_user():
    if current_user.role != 2:
        flash('无管理员权限！', 'danger')
        return redirect(url_for('auth.dashboard'))

    form = UserForm()
    if form.validate_on_submit():
        new_user = User(
            username=form.username.data,
            role=form.role.data,
            create_time=datetime.now()  # 补充创建时间
        )
        try:
            new_user.set_password(form.password.data)
        except AttributeError as e:
            flash('用户模型中缺少密码处理方法，无法保存密码！', 'danger')
            current_app.logger.error(f"密码加密失败: {e}")
            return redirect(url_for('admin.user_manage'))

        db.session.add(new_user)

        # ✅ [日志]
        role_map = {0: '学生', 1: '教师', 2: '管理员'}
        role_text = role_map.get(new_user.role, '未知')
        log_operation(f"新增了用户: {new_user.username} (角色: {role_text})")

        db.session.commit()
        flash(f'用户【{form.username.data}】添加成功', 'success')
        return redirect(url_for('admin.user_manage'))

    # 优化GET请求处理，避免重复重定向
    if form.errors:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{form[field].label.text}: {error}', 'danger')

    # 渲染用户管理页并携带表单
    all_users = User.query.order_by(User.id.desc()).all()
    return render_template('admin/user_manage.html',
                           all_users=all_users,
                           form=form)


@admin_bp.route('/user/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != 2:
        return jsonify({'code': 403, 'msg': '无权限操作！'})

    user_to_delete = User.query.get(user_id)
    if not user_to_delete:
        return jsonify({'code': 404, 'msg': '用户不存在！'})

    if user_to_delete.role == 2 or user_to_delete.id == current_user.id:
        return jsonify({'code': 400, 'msg': '不能删除管理员账户或您本人！'})

    try:
        # 1. 清理技能
        Skill.query.filter_by(user_id=user_id).delete()

        # 2. 清理课程 (teacher_id)
        Course.query.filter_by(teacher_id=user_id).update({'teacher_id': None})

        # 3. 清理证书关联
        Certificate.query.filter_by(user_id=user_id).update({'status': 3})  # 标记为已删除

        # ✅ [日志]
        log_operation(f"删除了用户: {user_to_delete.username} (ID: {user_id})")

        db.session.delete(user_to_delete)
        db.session.commit()
        return jsonify({'code': 200, 'msg': f'用户【{user_to_delete.username}】已删除！'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"删除用户失败: {e}")
        return jsonify({'code': 500, 'msg': f'删除失败: {str(e)}'})


@admin_bp.route('/user_manage')
@login_required
def user_manage():
    if current_user.role != 2:
        flash('无管理员权限！', 'danger')
        return redirect(url_for('auth.dashboard'))

    form = UserForm()
    all_users = User.query.order_by(User.id.desc()).all()

    return render_template('admin/user_manage.html',
                           all_users=all_users,
                           form=form)


@admin_bp.route('/system_setting')
@login_required
def system_setting():
    if current_user.role != 2:
        flash('无管理员权限！', 'danger')
        return redirect(url_for('auth.dashboard'))
    return render_template('admin/system_setting.html')


@admin_bp.route('/data_analysis')
@login_required
def data_analysis():
    if current_user.role != 2:
        flash('无管理员权限！', 'danger')
        return redirect(url_for('auth.dashboard'))

    # 使用count()提升查询效率，避免加载所有数据
    student_count = User.query.filter_by(role=0).count()
    teacher_count = User.query.filter_by(role=1).count()
    admin_count = User.query.filter_by(role=2).count()
    course_count = Course.query.count()
    skill_count = Skill.query.count()

    # 新增课程学分分布统计
    credit_stats = defaultdict(int)
    courses = Course.query.all()
    for course in courses:
        credit_stats[course.credit] += 1
    credit_labels = list(credit_stats.keys())
    credit_data = list(credit_stats.values())

    return render_template('admin/data_analysis.html',
                           student_count=student_count,
                           teacher_count=teacher_count,
                           admin_count=admin_count,
                           course_count=course_count,
                           skill_count=skill_count,
                           credit_labels=credit_labels,
                           credit_data=credit_data)


# -------------------------- 技能管理核心修复 --------------------------
@admin_bp.route('/add_skill', methods=['GET', 'POST'])  # 显式允许GET+POST
@login_required
def add_skill():
    """添加公共技能 - 核心修复：允许GET+POST，适配表单提交"""
    if current_user.role != 2:
        flash('无管理员权限！', 'danger')
        return redirect(url_for('auth.dashboard'))

    form = AdminSkillForm()  # 使用简化的技能表单
    if request.method == 'POST':
        # 兼容表单提交和AJAX提交
        skill_name = request.form.get('skill_name', '').strip()
        if not skill_name:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'code': 400, 'msg': '技能名称不能为空'})
            flash('技能名称不能为空！', 'warning')
            return redirect(url_for('admin.skill_manage'))

        # 检查技能是否已存在（避免重复）
        existing_skill = Skill.query.filter_by(name=skill_name, user_id=0).first()
        if existing_skill:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'code': 400, 'msg': '该技能已存在！'})
            flash(f'技能【{skill_name}】已存在！', 'warning')
            return redirect(url_for('admin.skill_manage'))

        # 添加公共技能（user_id=0标识）
        new_skill = Skill(
            name=skill_name,
            user_id=0,  # 公共技能标识
            current_level=1,
            create_time=datetime.now()
        )
        db.session.add(new_skill)

        # 记录日志
        log_operation(f"添加了公共技能: {skill_name}")

        db.session.commit()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'code': 200, 'msg': f'技能【{skill_name}】已添加到库中！'})
        flash(f'技能【{skill_name}】已添加到库中！', 'success')
        return redirect(url_for('admin.skill_manage'))

    # GET请求：渲染技能管理页并携带表单
    public_skills = Skill.query.filter_by(user_id=0).order_by(Skill.create_time.desc()).all()
    return render_template('admin/skill_manage.html',
                           public_skills=public_skills,
                           form=form)


@admin_bp.route('/skill_manage')
@login_required
def skill_manage():
    """技能管理列表页 - 核心修复：确保查询公共技能并传递表单"""
    if current_user.role != 2:
        flash('无管理员权限！', 'danger')
        return redirect(url_for('auth.dashboard'))

    # 查询公共技能（user_id=0）
    public_skills = Skill.query.filter_by(user_id=0).order_by(Skill.create_time.desc()).all()
    # 传递空表单（用于添加技能）
    form = AdminSkillForm()

    return render_template('admin/skill_manage.html',
                           public_skills=public_skills,
                           form=form)  # 必须传递表单


# 修复前的错误路由（缺少skill_id参数）：
# @admin_bp.route('/skill/delete', methods=['POST'])
# 修复后的路由（显式指定skill_id参数）：
@admin_bp.route('/skill/delete/<int:skill_id>', methods=['POST'])
@login_required
def delete_skill(skill_id):
    """删除公共技能 - 修复URL参数问题"""
    if current_user.role != 2:
        return jsonify({'code': 403, 'msg': '无权限操作！'})

    # 直接使用路由参数skill_id，无需再从表单/GET获取
    skill = Skill.query.filter_by(id=skill_id, user_id=0).first()
    if not skill:
        return jsonify({'code': 404, 'msg': '公共技能不存在！'})

    try:
        # 记录日志
        log_operation(f"删除了公共技能: {skill.name} (ID: {skill_id})")

        db.session.delete(skill)
        db.session.commit()
        return jsonify({'code': 200, 'msg': f'技能【{skill.name}】已删除！'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"删除技能失败: {e}")
        return jsonify({'code': 500, 'msg': f'删除失败: {str(e)}'})


# -------------------------- 其他路由 --------------------------
@admin_bp.route('/user/detail/<int:user_id>')
@login_required
def user_detail(user_id):
    if current_user.role != 2:
        flash('无管理员权限！', 'danger')
        return redirect(url_for('auth.dashboard'))

    user = User.query.filter_by(id=user_id).first_or_404()

    user_skills = []
    user_courses = []
    taught_courses = []
    research_direction = "未设置研究方向"

    if user.role == 0:  # 学生
        user_skills = user.skills if hasattr(user, 'skills') else []
        user_courses = user.selected_courses if hasattr(user, 'selected_courses') else []

    elif user.role == 1:  # 教师
        teacher_info = Teacher.query.filter_by(user_id=user.id).first()
        if teacher_info and hasattr(teacher_info, 'research_direction') and teacher_info.research_direction:
            research_direction = teacher_info.research_direction

        taught_courses = Course.query.filter_by(teacher_id=user.id).all()

    return render_template('admin/user_detail.html',
                           user=user,
                           skills=user_skills,
                           courses=user_courses,
                           taught_courses=taught_courses,
                           research_direction=research_direction
                           )


@admin_bp.route('/student/<int:student_id>/add_skill', methods=['GET', 'POST'])
@login_required
def add_student_skill(student_id):
    if current_user.role != 2:
        flash('无管理员权限！', 'danger')
        return redirect(url_for('auth.dashboard'))

    student = User.query.filter_by(id=student_id, role=0).first_or_404()
    form = SkillForm()
    form.submit.label.text = '新增学生技能'

    if form.validate_on_submit():
        existing_skill = Skill.query.filter_by(name=form.name.data, user_id=student_id).first()
        if existing_skill:
            flash(f'学生 {student.username} 已经拥有技能【{form.name.data}】！', 'danger')
            return redirect(url_for('admin.user_detail', user_id=student_id))

        new_skill = Skill(
            name=form.name.data,
            current_level=form.current_level.data,
            target_level=form.target_level.data,
            user_id=student_id,
            create_time=datetime.now()
        )
        db.session.add(new_skill)

        # ✅ [日志]
        log_operation(f"为学生 {student.username} (ID: {student.id}) 添加了技能: {new_skill.name}")

        db.session.commit()
        flash(f'成功为学生【{student.username}】添加技能【{new_skill.name}】！', 'success')
        return redirect(url_for('admin.user_detail', user_id=student_id))

    return render_template('admin/add_student_skill.html',
                           student=student,
                           form=form)


@admin_bp.route('/pending_certificates')
@login_required
@role_required(2)  # 管理员权限装饰器
def pending_certificates():
    """取消待审核证明页面，直接跳转至管理员信箱"""
    flash('所有待审核证明已移至消息列表中处理', 'info')
    return redirect(url_for('admin.mailbox_index'))  # 跳转至管理员信箱

@admin_bp.route('/certificates/review/<int:cert_id>', methods=['GET', 'POST'])
@login_required
@role_required(2)
def review_certificate(cert_id):
    cert = Certificate.query.get_or_404(cert_id)

    if request.method == 'GET':
        return render_template('admin/review_certificate.html', cert=cert)

    action = request.form.get('action')
    remarks = request.form.get('remarks', '')

    status_text = "未知操作"
    if action == 'approve':
        cert.status = 1
        status_text = "通过"
    elif action == 'reject':
        cert.status = 2
        status_text = "驳回"
    else:
        flash('无效的审核操作！', 'danger')
        return redirect(url_for('admin.mailbox_index'))

    # 仅当remarks有值时更新
    if remarks and hasattr(cert, 'remarks'):
        cert.remarks = remarks

    # 更新审核时间
    if hasattr(cert, 'review_time'):
        cert.review_time = datetime.now()

    # 标记相关通知为已读
    try:
        related_notifications = Notification.query.filter(
            Notification.recipient_id == current_user.id,
            Notification.content.contains(f"certificates/review/{cert_id}"),
            Notification.is_read == False
        ).all()

        for note in related_notifications:
            note.is_read = True

        # ✅ [日志]
        log_operation(f"{status_text}了用户 {cert.user.username} 的学习证明 (ID: {cert.id})")

        db.session.commit()
        flash('审核完成，相关通知已设为已读。', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"审核证书失败: {e}")
        flash(f'审核失败: {str(e)}', 'danger')
        return render_template('admin/review_certificate.html', cert=cert)

    return redirect(url_for('admin.mailbox_index'))


@admin_bp.route('/system/logs')
@login_required
def system_logs():
    if current_user.role != 2:
        flash('无权限访问', 'danger')
        return redirect(url_for('auth.dashboard'))

    # 分页查询日志，避免加载过多数据
    page = request.args.get('page', 1, type=int)
    per_page = 20
    logs_pagination = SystemLog.query.order_by(SystemLog.create_time.desc()).paginate(page=page, per_page=per_page)

    return render_template('admin/logs.html',
                           logs=logs_pagination.items,
                           pagination=logs_pagination)


# --- 课程管理模块 ---
@admin_bp.route('/course_manage')
@login_required
def course_manage():
    """课程管理列表页 - 最终强制修复（无任何报错）"""
    if current_user.role != 2:
        flash('无管理员权限！', 'danger')
        return redirect(url_for('auth.dashboard'))

    # 查询所有课程
    courses = Course.query.order_by(Course.create_time.desc()).all()

    # 遍历课程，强制添加 student_count 和 teacher_name 属性
    for course in courses:
        # 初始化默认值，避免未定义报错
        course.student_count = 0
        course.teacher_name = "未分配"

        # 统计选课人数（兼容所有场景）
        if hasattr(course, 'students'):
            # 无论 students 是 Query 对象还是列表，都转成列表后统计长度
            student_list = course.students.all() if hasattr(course.students, 'all') else course.students
            course.student_count = len(student_list)

        # 填充教师名称
        if hasattr(course, 'teacher') and course.teacher:
            course.teacher_name = course.teacher.username

    # 渲染模板（只传提前处理好的 courses）
    return render_template('admin/course_manage.html', courses=courses)


@admin_bp.route('/course/detail/<int:course_id>')
@login_required
def course_detail(course_id):
    """查看课程详情及选课学生名单"""
    if current_user.role != 2:
        flash('无管理员权限！', 'danger')
        return redirect(url_for('auth.dashboard'))

    course = Course.query.get_or_404(course_id)
    # 兼容处理：获取学生列表（无论类型）
    if hasattr(course, 'students'):
        try:
            # Query对象可排序
            enrolled_students = course.students.order_by(User.username).all()
        except AttributeError:
            # 列表直接使用
            enrolled_students = course.students
    else:
        enrolled_students = []

    return render_template('admin/course_detail.html',
                           course=course,
                           students=enrolled_students,
                           student_count=len(enrolled_students))


@admin_bp.route('/course/edit/<int:course_id>', methods=['GET', 'POST'])
@login_required
def edit_course(course_id):
    """编辑课程：修改信息、指派老师"""
    if current_user.role != 2:
        flash('无管理员权限！', 'danger')
        return redirect(url_for('auth.dashboard'))

    course = Course.query.get_or_404(course_id)
    teachers = User.query.filter_by(role=1).order_by(User.username).all()

    if request.method == 'POST':
        try:
            new_name = request.form.get('name', '').strip()
            new_credit = request.form.get('credit', '').strip()
            new_teacher_id = request.form.get('teacher_id', '0')

            if not new_name or not new_credit:
                flash('课程名称和学分不能为空', 'danger')
                return redirect(url_for('admin.edit_course', course_id=course.id))

            # 校验学分格式
            new_credit = float(new_credit)
            if new_credit < 0.5 or new_credit > 10:
                flash('学分需在0.5-10之间', 'danger')
                return redirect(url_for('admin.edit_course', course_id=course.id))

            # 更新课程信息
            old_name = course.name
            course.name = new_name
            course.credit = new_credit
            course.update_time = datetime.now()  # 补充更新时间

            teacher_name = "无"
            if new_teacher_id and new_teacher_id != '0':
                teacher = User.query.get(int(new_teacher_id))
                if teacher:
                    course.teacher_id = teacher.id
                    teacher_name = teacher.username
            else:
                course.teacher_id = None

            # ✅ [日志]
            log_operation(f"修改课程 '{old_name}' -> '{course.name}' (ID:{course.id}): 指派给 {teacher_name}")

            db.session.commit()
            flash('课程信息已更新', 'success')
        except ValueError:
            flash('学分必须是数字格式', 'danger')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"编辑课程失败: {e}")
            flash(f'编辑失败: {str(e)}', 'danger')

        return redirect(url_for('admin.course_manage'))

    return render_template('admin/edit_course.html', course=course, teachers=teachers)


@admin_bp.route('/course/delete/<int:course_id>', methods=['POST'])
@login_required
def delete_course(course_id):
    """删除课程 - 优化返回格式"""
    if current_user.role != 2:
        return jsonify({'code': 403, 'msg': '无权限'})

    course = Course.query.get(course_id)
    if not course:
        return jsonify({'code': 404, 'msg': '课程不存在'})

    course_name = course.name

    try:
        # ✅ [日志]
        log_operation(f"删除了课程: {course_name} (ID:{course_id})")

        db.session.delete(course)
        db.session.commit()
        return jsonify({'code': 200, 'msg': f'课程 {course_name} 已删除'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"删除课程失败: {e}")
        return jsonify({'code': 500, 'msg': f'删除失败: {str(e)}'})


# -------------------------- 管理员信箱核心修复 --------------------------
@admin_bp.route('/mailbox')
@login_required
@role_required(2)  # 补充缺失的参数：2=管理员权限
def mailbox_index():
    """管理员信箱：复用 student 的 mailbox/index.html 模板"""
    # 查询管理员的所有通知
    notifications = Notification.query.filter_by(recipient_id=current_user.id).order_by(
        Notification.is_read.asc(),
        Notification.timestamp.desc()
    ).all()

    # 传递 is_admin=True 标识，让模板适配管理员功能
    return render_template('mailbox/index.html',
                           notifications=notifications,
                           is_admin=True)  # 核心：新增管理员标识


# 补充管理员专属的“标记已读/删除/回复”路由（与 student 蓝图路由名对齐）
@admin_bp.route('/notification/mark_read/<int:notification_id>')
@login_required
@role_required(2)  # 补充缺失的参数
def mark_notification_read(notification_id):
    """管理员标记通知为已读（路由名与 student 一致）"""
    notice = Notification.query.get_or_404(notification_id)
    if notice.recipient_id == current_user.id:
        notice.is_read = True
        db.session.commit()
        flash('消息已标为已读', 'info')
    return redirect(url_for('admin.mailbox_index'))


@admin_bp.route('/notification/delete/<int:notification_id>', methods=['POST'])
@login_required
@role_required(2)  # 补充缺失的参数
def delete_notification(notification_id):
    """管理员删除通知（路由名与 student 一致）"""
    notice = Notification.query.get_or_404(notification_id)
    if notice.recipient_id == current_user.id:
        db.session.delete(notice)
        db.session.commit()
        flash('消息已删除', 'success')
    return redirect(url_for('admin.mailbox_index'))


@admin_bp.route('/notification/reply/<int:notification_id>', methods=['POST'])
@login_required
@role_required(2)  # 补充缺失的参数
def reply_notification(notification_id):
    """管理员回复通知（路由名与 student 一致）"""
    original_notif = Notification.query.get_or_404(notification_id)
    reply_content = request.form.get('reply_content')

    if not reply_content:
        flash('回复内容不能为空', 'warning')
        return redirect(url_for('admin.mailbox_index'))

    # 回复给原发送者
    recipient_id = original_notif.sender_id or User.query.filter_by(role=2).first().id
    new_reply = Notification(
        sender_id=current_user.id,
        recipient_id=recipient_id,
        title=f"回复: {original_notif.title}",
        content=f"管理员回复：\n{reply_content}",
        is_read=False,
        timestamp=datetime.now()
    )
    db.session.add(new_reply)
    db.session.commit()
    flash('回复已发送', 'success')
    return redirect(url_for('admin.mailbox_index'))


# 审核通过证明路由（修复 save() 方法缺失问题）
@admin_bp.route('/certificate/approve/<int:cert_id>', methods=['POST'])
@login_required
@role_required(2)  # 补充缺失的参数
def approve_certificate(cert_id):
    cert = Certificate.query.get_or_404(cert_id)
    cert.status = 1
    cert.review_time = datetime.now()

    # 修复：移除 save() 方法，改用 db.session.add()
    notice = Notification(
        sender_id=current_user.id,
        recipient_id=cert.user_id,
        title="学习证明审核通过",
        content=f"您的「{cert.description}」证明已通过审核",
        is_read=False,
        timestamp=datetime.now()
    )
    db.session.add(notice)  # 替换 save() 方法
    db.session.commit()

    flash(f"证明「{cert.description}」审核通过", "success")
    return redirect(url_for('admin.mailbox_index'))  # 跳转到管理员信箱


# 补充审核拒绝证明路由（完整逻辑）
@admin_bp.route('/certificate/reject/<int:cert_id>', methods=['POST'])
@login_required
@role_required(2)
def reject_certificate(cert_id):
    cert = Certificate.query.get_or_404(cert_id)
    cert.status = 2
    cert.review_time = datetime.now()

    # 发送拒绝通知给学生
    notice = Notification(
        sender_id=current_user.id,
        recipient_id=cert.user_id,
        title="学习证明审核拒绝",
        content=f"您的「{cert.description}」证明审核未通过，请检查内容后重新提交",
        is_read=False,
        timestamp=datetime.now()
    )
    db.session.add(notice)
    db.session.commit()

    flash(f"证明「{cert.description}」审核拒绝", "warning")
    return redirect(url_for('admin.mailbox_index'))
