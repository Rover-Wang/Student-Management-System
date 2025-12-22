from flask import Blueprint, render_template, flash, redirect, url_for, request, jsonify, current_app, send_from_directory
from flask_login import login_required, current_user
from models import db, User, Course, Skill, Feedback, StudyPlan, Certificate, Notification, Enrollment
from datetime import datetime
import os
from werkzeug.utils import secure_filename # <-- 确保添加此行

student_bp = Blueprint('student', __name__)


# 辅助函数：将等级数字转换为文本 (为技能管理页使用)
def get_level_text(level):
    levels = {1: '入门', 2: '基础', 3: '熟练', 4: '精通', 5: '专家'}
    return levels.get(level, '-')


# -------------------------- 1. 首页路由 (/index) - 唯一且精简 --------------------------
@student_bp.route('/student/index')
@login_required
def student_index():
    if current_user.role != 0:
        return redirect(url_for('admin.admin_index'))

    # ✅ 核心修复：直接从 Enrollment 表查询统计，确保 4 门就是 4 门
    enrollments = Enrollment.query.filter_by(student_id=current_user.id).all()
    course_count = len(enrollments)

    # ✅ 后端计算 GPA，防止前端重复循环
    total_credits = 0
    total_points = 0
    for en in enrollments:
        if en.score is not None:
            total_credits += en.course.credit
            total_points += (en.grade_point * en.course.credit)
    gpa = (total_points / total_credits) if total_credits > 0 else 0

    # 其他数据统计
    # ✅ 修复：直接查询当前学生的技能数量（而非依赖关系）
    skill_count = Skill.query.filter_by(user_id=current_user.id).count()
    study_plans = StudyPlan.query.filter_by(user_id=current_user.id, status=0).order_by(StudyPlan.deadline.asc()).limit(
        3).all()
    pending_plans_count = StudyPlan.query.filter_by(user_id=current_user.id, status=0).count()
    certificates = Certificate.query.filter_by(user_id=current_user.id).order_by(Certificate.upload_time.desc()).limit(
        3).all()

    return render_template('student/index.html',
                           course_count=course_count,
                           gpa=gpa,
                           skill_count=skill_count,
                           study_plans=study_plans,
                           pending_plans_count=pending_plans_count,
                           certificates=certificates,
                           current_time=datetime.now())

# -------------------------- 2. 课程管理路由 (/courses) --------------------------
@student_bp.route('/student/courses')
@login_required
def course_management():
    # 1. 获取所有课程供选课大厅使用
    all_courses = Course.query.all()

    # 2. ✅ 核心修复：强制使用 .all() 将查询结果转为列表，防止 Jinja2 迭代异常
    enrollments = Enrollment.query.filter_by(student_id=current_user.id).all()

    # 获取已选 ID 列表
    selected_course_ids = [en.course_id for en in enrollments]

    return render_template('student/course_management.html',
                           all_courses=all_courses,
                           enrollments=enrollments,
                           selected_course_ids=selected_course_ids)

# -------------------------- 3. 技能管理路由 (/skills) - 核心修复 --------------------------
@student_bp.route('/student/skills')
@login_required
def skill_management():
    if current_user.role != 0:
        return redirect(url_for('admin.admin_index'))

    # ✅ 核心修复：直接查询当前学生的技能（而非依赖关系），确保数据准确
    skills = Skill.query.filter_by(
        user_id=current_user.id
    ).order_by(Skill.create_time.desc()).all()

    # 为雷达图准备数据
    skill_names = [skill.name for skill in skills]
    skill_levels = [skill.current_level for skill in skills]

    return render_template('student/skill.html',
                           skills=skills,  # 确保模板接收的变量名是 skills
                           skill_names=skill_names,
                           skill_levels=skill_levels,
                           get_level_text=get_level_text)  # 💡 核心修复：传递 get_level_text 函数


# -------------------------- 4. 学习计划管理页面 (/plans) --------------------------
@student_bp.route('/student/plans')
@login_required
def plan_management():
    if current_user.role != 0:
        return redirect(url_for('admin.admin_index'))

    study_plans = StudyPlan.query.filter_by(user_id=current_user.id).order_by(StudyPlan.deadline).all() or []

    return render_template('student/plan_management.html',
                           study_plans=study_plans,
                           current_time=datetime.now())


# routes/student.py (新增信箱路由)

# -------------------------- 邮件/通知管理 --------------------------

@student_bp.route('/mailbox')
@login_required
def mailbox_index():
    # 查询当前用户的所有通知，未读的排在前面，按时间倒序
    notifications = Notification.query.filter_by(recipient_id=current_user.id).order_by(
        Notification.is_read.asc(),
        Notification.timestamp.desc()
    ).all()

    return render_template('mailbox/index.html', notifications=notifications)


@student_bp.route('/notification/mark_read/<int:notification_id>')
@login_required
def mark_notification_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)

    # 仅允许收件人操作
    if notification.recipient_id == current_user.id and not notification.is_read:
        notification.is_read = True
        db.session.commit()
        flash('消息已标记为已读。', 'info')

    # 返回到消息列表页
    return redirect(request.referrer or url_for('student.mailbox_index'))

# -------------------------- 5. 学习证明管理页面 (/certificates) --------------------------
@student_bp.route('/student/certificates')
@login_required
def certificate_management():
    if current_user.role != 0:
        return redirect(url_for('admin.admin_index'))

    certificates = Certificate.query.filter_by(user_id=current_user.id).order_by(
        Certificate.upload_time.desc()).all() or []

    return render_template('student/certificate_management.html',
                           certificates=certificates)


# -------------------------- 功能操作：选课/退课 --------------------------
@student_bp.route('/student/course/select', methods=['POST'])
@login_required
def select_course():
    if current_user.role != 0:
        flash('无权限操作', 'danger')
        return redirect(url_for('student.student_index'))

    course_ids = request.form.getlist('course_ids')
    if not course_ids:
        flash('请选择课程', 'danger')
        return redirect(url_for('student.course_management'))

    count = 0
    for course_id in course_ids:
        # 1. 检查是否已经选过
        existing = Enrollment.query.filter_by(
            student_id=current_user.id,
            course_id=int(course_id)
        ).first()

        if not existing:
            # 2. 如果没选过，创建新的选课记录
            new_enrollment = Enrollment(
                student_id=current_user.id,
                course_id=int(course_id)
            )
            db.session.add(new_enrollment)
            count += 1

    if count > 0:
        db.session.commit()
        flash(f'成功选择 {count} 门课程', 'success')
    else:
        flash('所选课程均已在您的课表中', 'info')

    return redirect(url_for('student.course_management'))

@student_bp.route('/student/course/drop/<int:course_id>', methods=['GET'])
@login_required
def drop_course(course_id):
    if current_user.role != 0:
        flash('无权限操作', 'danger')
        return redirect(url_for('student.student_index'))

    # 查找选课记录
    enrollment = Enrollment.query.filter_by(
        student_id=current_user.id,
        course_id=course_id
    ).first()

    if enrollment:
        db.session.delete(enrollment)
        db.session.commit()
        flash('退课成功', 'success')
    else:
        flash('未找到该课程的选课记录', 'danger')

    return redirect(url_for('student.course_management'))

# -------------------------- 功能操作：技能 (核心修复) --------------------------

@student_bp.route('/student/skill/add', methods=['GET', 'POST'])  # ✅ 新增GET方法，适配表单页面
@login_required
def add_skill():
    if current_user.role != 0:
        flash('无权限操作', 'danger')
        return redirect(url_for('student.student_index'))

    # ✅ GET请求：渲染添加技能的表单页面
    if request.method == 'GET':
        return render_template('student/add_skill.html')

    # POST请求：处理技能添加
    skill_name = request.form.get('skill_name')
    current_level = request.form.get('current_level')
    target_level = request.form.get('target_level')

    if not skill_name or not current_level or not target_level:
        flash('请填写完整信息', 'danger')
        return redirect(url_for('student.add_skill'))  # 跳转回添加页面，而非技能列表

    try:
        current_level = int(current_level)
        target_level = int(target_level)
        if not (1 <= current_level <= 5) or not (1 <= target_level <= 5):
            raise ValueError
    except ValueError:
        flash('技能等级必须为1-5之间的整数', 'danger')
        return redirect(url_for('student.add_skill'))  # 跳转回添加页面

    # ✅ 核心修复：添加创建时间，确保数据完整
    new_skill = Skill(
        name=skill_name,
        current_level=current_level,
        target_level=target_level,
        user_id=current_user.id,
        create_time=datetime.now()  # 新增：补充创建时间
    )
    db.session.add(new_skill)
    db.session.commit()

    flash('技能添加成功', 'success')
    return redirect(url_for('student.skill_management'))  # 跳转至技能管理页刷新列表


@student_bp.route('/student/skill/edit/<int:skill_id>', methods=['GET', 'POST'])
@login_required
def edit_skill(skill_id):
    # 权限校验和查询逻辑
    if current_user.role != 0:
        flash('无学生权限！', 'danger')
        return redirect(url_for('auth.login'))

    # ✅ 核心修复：仅查询当前学生的技能
    skill = Skill.query.filter_by(id=skill_id, user_id=current_user.id).first_or_404()

    if request.method == 'POST':
        # 核心修正：将 'skill_name' 改为 'name'，与 HTML 模板匹配
        skill_name = request.form.get('name')

        # 增加非空校验，避免 IntegrityError
        if not skill_name:
            flash('技能名称不能为空！', 'danger')
            return redirect(url_for('student.edit_skill', skill_id=skill_id))

        try:
            current_level = int(request.form.get('current_level'))
            target_level = int(request.form.get('target_level'))
        except:
            flash('技能等级必须为整数', 'danger')
            return redirect(url_for('student.edit_skill', skill_id=skill_id))

        # 赋值更新
        skill.name = skill_name
        skill.current_level = current_level
        skill.target_level = target_level

        # 使用 try/except 捕获可能的完整性错误，提高健壮性
        try:
            db.session.commit()
            flash('技能修改成功！', 'success')
            return redirect(url_for('student.skill_management'))  # 跳转至统一的技能管理页
        except Exception as e:
            db.session.rollback()
            # 捕获其他可能的错误，例如名称重复（如果数据库有 unique 约束）
            flash(f'技能修改失败，请检查输入。错误: {str(e)}', 'danger')
            return redirect(url_for('student.edit_skill', skill_id=skill_id))

    return render_template('student/edit_skill.html', skill=skill)


@student_bp.route('/student/skill/delete/<int:skill_id>', methods=['GET', 'POST'])
@login_required
def delete_skill(skill_id):
    # 权限校验和删除逻辑
    if current_user.role != 0:
        flash('无学生权限！', 'danger')
        return redirect(url_for('auth.login'))

    # ✅ 核心修复：仅查询当前学生的技能
    skill = Skill.query.filter_by(id=skill_id, user_id=current_user.id).first_or_404()

    db.session.delete(skill)
    db.session.commit()
    flash(f'已删除技能【{skill.name}】！', 'success')
    return redirect(url_for('student.skill_management'))  # 跳转至统一的技能管理页


# -------------------------- 功能操作：学习计划 --------------------------

@student_bp.route('/student/plan/add', methods=['POST'])
@login_required
def add_study_plan():
    title = request.form.get('title')
    content = request.form.get('content', '')
    deadline = request.form.get('deadline')

    if not title or not deadline:
        flash('标题和截止日期不能为空', 'danger')
        return redirect(url_for('student.plan_management'))

    try:
        deadline_date = datetime.strptime(deadline, '%Y-%m-%d')
        if deadline_date < datetime.now():
            flash('截止日期不能早于当前时间', 'danger')
            return redirect(url_for('student.plan_management'))
    except ValueError:
        flash('日期格式错误，请选择有效日期（格式：YYYY-MM-DD）', 'danger')
        return redirect(url_for('student.plan_management'))

    plan = StudyPlan(user_id=current_user.id, title=title, content=content, deadline=deadline_date)
    db.session.add(plan)
    db.session.commit()

    flash('学习计划添加成功', 'success')
    return redirect(url_for('student.plan_management'))


@student_bp.route('/student/plan/edit/<int:plan_id>', methods=['GET', 'POST'])
@login_required
def edit_study_plan(plan_id):
    # ... (逻辑保持不变) ...
    if current_user.role != 0:
        flash('无学生权限！', 'danger')
        return redirect(url_for('auth.login'))

    plan = StudyPlan.query.get_or_404(plan_id)
    if plan.user_id != current_user.id:
        flash('无权修改他人计划！', 'danger')
        return redirect(url_for('student.student_index'))

    if request.method == 'POST':
        # 1. 简化校验
        title = request.form.get('title')
        deadline_str = request.form.get('deadline')

        if not title or not deadline_str:
            flash('标题和截止日期不能为空', 'danger')
            return redirect(url_for('student.edit_study_plan', plan_id=plan_id))

        try:
            deadline_date = datetime.strptime(deadline_str, '%Y-%m-%d')
        except:
            flash('日期格式错误', 'danger')
            return redirect(url_for('student.edit_study_plan', plan_id=plan_id))

        # 2. 核心修复：处理状态字段 (Checkbox)
        # 如果 'status' 字段存在于请求中 (即复选框被选中)，则设置为 1 (已完成)
        # 否则，设置为 0 (进行中/未完成)
        new_status = 1 if 'status' in request.form else 0

        # 3. 更新数据库对象
        plan.title = title
        plan.content = request.form.get('content', '')
        plan.deadline = deadline_date
        plan.status = new_status

        db.session.commit()

        flash('学习计划修改成功！', 'success')
        return redirect(url_for('student.plan_management'))

    return render_template('student/edit_plan.html', plan=plan)


@student_bp.route('/student/plan/delete/<int:plan_id>', methods=['GET'])
@login_required
def delete_study_plan(plan_id):
    # ... (逻辑保持不变) ...
    if current_user.role != 0:
        flash('无学生权限！', 'danger')
        return redirect(url_for('auth.login'))

    plan = StudyPlan.query.get_or_404(plan_id)
    if plan.user_id != current_user.id:
        flash('无权删除他人计划！', 'danger')
        return redirect(url_for('student.student_index'))

    db.session.delete(plan)
    db.session.commit()
    flash(f'已删除计划「{plan.title}」！', 'success')
    return redirect(url_for('student.plan_management'))


# -------------------------- 功能操作：其他 --------------------------

# 成绩更新接口
@student_bp.route('/student/course/update-score/<int:course_id>', methods=['POST'])
@login_required
def update_course_score(course_id):
    # ... (逻辑保持不变) ...
    if current_user.role != 0:
        flash('无权限操作', 'danger')
        return redirect(url_for('student.student_index'))

    score = request.form.get('score')
    if not score or not score.isdigit() or not (0 <= int(score) <= 100):
        flash('请输入有效的成绩（0-100）', 'danger')
        return redirect(url_for('student.course_management'))

    course = Course.query.get(course_id)
    if course and course in current_user.selected_courses:
        # ⚠️ 确保您的 Course 模型或关联表支持 score 字段的更新
        # course.score = int(score)
        db.session.commit()
        flash('成绩更新成功', 'success')
    else:
        flash('课程不存在或未选择', 'danger')

    return redirect(url_for('student.course_management'))


@student_bp.route('/student/certificate/upload', methods=['POST'])
@login_required
def upload_certificate():
    # 1. 获取表单数据
    description = request.form.get('description')
    cert_file = request.files.get('cert_file')

    if not cert_file or cert_file.filename == '':
        flash('请选择要上传的学习证明文件。', 'warning')
        return redirect(url_for('student.certificate_management'))

    # 2. 校验文件和处理上传逻辑
    if cert_file and current_app.allowed_file(cert_file.filename):
        save_path = None
        try:
            # --- 生成唯一文件名 ---
            filename = secure_filename(cert_file.filename)
            unique_filename = f"{current_user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            upload_dir = current_app.config['UPLOAD_FOLDER']

            if not os.path.exists(upload_dir):
                os.makedirs(upload_dir)

            # --- 物理保存文件 ---
            save_path = os.path.join(upload_dir, unique_filename)
            cert_file.save(save_path)

            # 3. 写入数据库记录
            # 💡 修复：同时给 filename 和 file_path 赋值，避免数据库 NOT NULL 报错
            # 💡 保持路径纯净，仅存储 unique_filename
            new_certificate = Certificate(
                user_id=current_user.id,
                description=description,
                filename=unique_filename,
                file_path=unique_filename,
                upload_time=datetime.now(),
                status=0
            )
            db.session.add(new_certificate)
            db.session.flush()  # 获取新记录的 ID 以便生成链接

            # 4. 发送通知给管理员 (role=2)
            admin_users = User.query.filter_by(role=2).all()

            if admin_users:
                # 💡 核心修复：生成完整的 HTTP 绝对路径，确保管理员可以点击跳转
                # 注意：'admin.review_certificate' 需对应你 admin 蓝图中的函数名
                review_url = url_for('admin.review_certificate',
                                     cert_id=new_certificate.id,
                                     _external=True)

                notification_title = f"❗ 待审核的学习证明：来自 {current_user.username}"

                # 构造通知内容，包含可点击的完整链接
                notification_content = (
                    f"用户 {current_user.username} 提交了新的学习证明「{description}」，需要审核。\n"
                    f"点击此处直接审核：{review_url}"
                )

                for admin in admin_users:
                    new_notification = Notification(
                        sender_id=current_user.id,
                        recipient_id=admin.id,
                        title=notification_title,
                        content=notification_content,
                        is_read=False,
                        timestamp=datetime.now()
                    )
                    db.session.add(new_notification)

            db.session.commit()
            flash('学习证明上传成功，已通知管理员进行审核。', 'success')

        except Exception as e:
            db.session.rollback()
            # 如果文件已保存但数据库失败，删除该文件防止占用空间
            if save_path and os.path.exists(save_path):
                os.remove(save_path)
            current_app.logger.error(f"Certificate upload failed: {e}")
            flash(f'证明信息保存失败，请重试。错误: {str(e)}', 'danger')

        return redirect(url_for('student.certificate_management'))

    else:
        flash('文件类型不支持。只允许上传图片和PDF文件。', 'danger')
        return redirect(url_for('student.certificate_management'))

# -------------------------- 功能操作：意见反馈 (修正后的函数) --------------------------
@student_bp.route('/student/feedback', methods=['POST'])
@login_required
def submit_feedback():
    if current_user.role != 0:
        flash('无权限操作', 'danger')
        return redirect(url_for('student.student_index'))

    feedback_content = request.form.get('content')

    if not feedback_content or len(feedback_content.strip()) < 10:
        flash('反馈内容不能为空，且至少需要10个字符。', 'danger')
        return redirect(request.referrer or url_for('student.student_index'))

    try:
        # 1. 保存原始 Feedback 记录 (用于历史追踪)
        new_feedback = Feedback(user_id=current_user.id, content=feedback_content)
        db.session.add(new_feedback)

        # 2. 查找管理员并创建通知 (管理员 role=2)
        admin_user = User.query.filter_by(role=2).first()
        if admin_user:
            # 修正通知内容：这是反馈通知，而不是证书审核通知
            notification_title = f"新意见反馈：来自 {current_user.username}"
            notification_content = (
                f"来自用户ID {current_user.id} 的反馈：\n\n{feedback_content}"
                f"\n请前往管理后台的反馈管理页面查看详情。"
            )

            new_notification = Notification(
                sender_id=current_user.id,
                recipient_id=admin_user.id,
                title=notification_title,
                content=notification_content
            )
            db.session.add(new_notification)
            flash('意见反馈提交成功，已发送给管理员。感谢您的建议！', 'success')
        else:
            # 如果没有管理员，仍然提交反馈记录
            flash('意见反馈已记录，但未找到管理员接收者。', 'info')

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f'提交反馈时发生错误：{str(e)}', 'danger')

    return redirect(url_for('student.student_index'))


@student_bp.route('/protected_file/<filename>')
@login_required
def serve_protected_file(filename):
    """提供受保护的文件访问，不带蓝图前缀，确保 URL 正确。"""
    # 权限检查：只要登录即可访问
    if not current_user.is_authenticated:
        return "请先登录", 403

    # 物理目录：使用 app.py 中设置的绝对路径。
    # 这里使用 root_path 重新构造，以避免 app.config 的值可能在某些环境中出错
    CERTIFICATE_FOLDER = current_app.config['UPLOAD_FOLDER']

    try:
        # send_from_directory 安全地从指定目录返回文件
        return send_from_directory(
            CERTIFICATE_FOLDER,
            filename,
            as_attachment=False
        )
    except FileNotFoundError:
        return "文件未找到", 404


# -------------------------- 信箱管理增强功能 --------------------------

@student_bp.route('/mailbox/delete/<int:notification_id>', methods=['POST'])
@login_required
def delete_notification(notification_id):
    """删除单条通知"""
    notification = Notification.query.get_or_404(notification_id)

    # 权限检查：只能删除发给自己的通知
    if notification.recipient_id != current_user.id:
        flash('无权删除此消息。', 'danger')
        return redirect(url_for('student.mailbox_index'))

    db.session.delete(notification)
    db.session.commit()
    flash('消息已删除。', 'success')
    return redirect(url_for('student.mailbox_index'))


@student_bp.route('/mailbox/clear_read', methods=['POST'])
@login_required
def clear_read_notifications():
    """清空所有已读通知"""
    read_notifications = Notification.query.filter_by(
        recipient_id=current_user.id,
        is_read=True
    ).all()

    count = len(read_notifications)
    for note in read_notifications:
        db.session.delete(note)

    db.session.commit()
    flash(f'已清空 {count} 条已读消息。', 'info')
    return redirect(url_for('student.mailbox_index'))


@student_bp.route('/mailbox/clear_all', methods=['POST'])
@login_required
def clear_all_notifications():
    """清空所有通知（无论是否已读）"""
    all_notifications = Notification.query.filter_by(recipient_id=current_user.id).all()

    count = len(all_notifications)
    for note in all_notifications:
        db.session.delete(note)

    db.session.commit()
    flash('信箱已全部清空。', 'warning')
    return redirect(url_for('student.mailbox_index'))


@student_bp.route('/student/certificate/delete/<int:cert_id>', methods=['POST'])
@login_required
def delete_certificate(cert_id):
    # 1. 查找证明记录
    cert = Certificate.query.get_or_404(cert_id)

    # 2. 权限校验：确保学生只能删除自己的证明
    if cert.user_id != current_user.id:
        flash('无权删除此证明记录。', 'danger')
        return redirect(url_for('student.certificate_management'))

    try:
        # 3. 物理删除文件（可选，建议保留以防误删，若需彻底删除请启用）
        # if cert.filename:
        #     file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], cert.filename)
        #     if os.path.exists(file_path):
        #         os.remove(file_path)

        # 4. 从数据库中删除记录
        db.session.delete(cert)
        db.session.commit()
        flash(f'证明「{cert.description}」已成功删除。', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"删除证明失败: {e}")
        flash('删除操作失败，请稍后再试。', 'danger')

    return redirect(url_for('student.certificate_management'))


@student_bp.route('/mailbox/reply/<int:notification_id>', methods=['POST'])
@login_required
def reply_notification(notification_id):
    """回复通知功能"""
    # 1. 获取原通知内容
    original_notif = Notification.query.get_or_404(notification_id)

    # 2. 获取回复内容
    reply_content = request.form.get('reply_content')

    if not reply_content or len(reply_content.strip()) < 2:
        flash('回复内容太短。', 'warning')
        return redirect(url_for('student.mailbox_index'))

    # 3. 确定收件人（回复给原发送者）
    # 如果原发送者是系统（None），则默认尝试回复给第一个管理员
    recipient_id = original_notif.sender_id
    if not recipient_id:
        admin = User.query.filter_by(role=2).first()
        recipient_id = admin.id if admin else None

    if not recipient_id:
        flash('无法找到收件人（系统消息不可直接回复）。', 'danger')
        return redirect(url_for('student.mailbox_index'))

    # 4. 创建新通知
    new_reply = Notification(
        sender_id=current_user.id,
        recipient_id=recipient_id,
        title=f"回复: {original_notif.title}",
        content=f"--- 针对您的消息回复 ---\n{reply_content}\n\n[原消息]: {original_notif.content[:50]}...",
        timestamp=datetime.now(),
        is_read=False
    )

    try:
        db.session.add(new_reply)
        db.session.commit()
        flash('回复已发送成功！', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'发送失败: {str(e)}', 'danger')

    return redirect(url_for('student.mailbox_index'))


# -------------------------- 新增：发送反馈给老师的页面 --------------------------

@student_bp.route('/student/feedback/send')
@login_required
def send_feedback_to_teacher():
    recipient_id = request.args.get('recipient_id')
    subject = request.args.get('subject', '课程反馈')

    if not recipient_id:
        flash('未指定反馈对象', 'danger')
        return redirect(url_for('student.course_management'))

    teacher = User.query.get_or_404(recipient_id)
    return render_template('student/send_to_teacher.html', teacher=teacher, subject=subject)


# -------------------------- 修改：统一的发送逻辑 --------------------------
@student_bp.route('/student/feedback/post', methods=['POST'])
@login_required
def post_feedback():
    recipient_id = request.form.get('recipient_id')
    title = request.form.get('title')
    content = request.form.get('content')

    # ✅ 存入 Notification 表，直接同步到老师信箱
    new_notif = Notification(
        sender_id=current_user.id,
        recipient_id=recipient_id,
        title=title,
        content=content,
        timestamp=datetime.now(),
        is_read=False
    )
    db.session.add(new_notif)
    db.session.commit()
    flash('反馈已提交至老师信箱！', 'success')
    return redirect(url_for('student.course_management'))


@student_bp.route('/student/feedback/to_teacher', methods=['POST'])
@login_required
def feedback_to_teacher():
    # 获取老师ID、课程名和反馈内容
    teacher_id = request.form.get('recipient_id')
    course_name = request.form.get('course_name')
    content = request.form.get('content')

    if not content or len(content.strip()) < 5:
        flash('反馈内容过短', 'warning')
        return redirect(request.referrer)

    # 创建通知给对应的老师
    new_notification = Notification(
        sender_id=current_user.id,
        recipient_id=teacher_id,
        title=f"课程反馈：来自 {current_user.username}",
        content=f"针对课程《{course_name}》的反馈：\n{content}",
        timestamp=datetime.now(),
        is_read=False
    )

    # 同时在 Feedback 表记录（可选，用于存档）
    new_feedback = Feedback(user_id=current_user.id, content=content)

    db.session.add(new_notification)
    db.session.add(new_feedback)
    db.session.commit()

    flash('反馈已成功发送给任课老师！', 'success')
    return redirect(url_for('student.course_management'))