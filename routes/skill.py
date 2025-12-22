from flask import Blueprint, render_template, flash, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from models import db, Skill, SkillRecord, User  # 确保 User 模型被导入
from datetime import datetime  # 确保 datetime 被导入

skill_bp = Blueprint('skill', __name__)


# 辅助函数：将等级数字转换为文本 (必须在文件内定义，以便被路由使用)
def get_level_text(level):
    levels = {1: '入门', 2: '基础', 3: '熟练', 4: '精通', 5: '专家'}
    return levels.get(level, '-')


# 学生技能追踪页 (修复后的路由)
@skill_bp.route('/student/skill')
@login_required
def student_skill():
    if current_user.role != 0:
        flash('无权限访问！')
        # 假设 auth.dashboard 是一个通用的首页或登录页
        return redirect(url_for('auth.login'))

    skills = Skill.query.filter_by(user_id=current_user.id).all()

    # 💡 核心修复：传递 get_level_text 给模板
    return render_template('student/skill.html',
                           skills=skills,
                           get_level_text=get_level_text)


# 添加技能（POST接口）
@skill_bp.route('/api/skill/add', methods=['POST'])
@login_required
def add_skill():
    if current_user.role != 0:
        return jsonify({'code': 403, 'msg': '无权限！'})

    # 注意：您的前端模板使用 form data 提交，而不是 JSON。
    # 假设您的前端使用的是 form data，因此这里修改为 request.form
    name = request.form.get('skill_name')
    current_level = request.form.get('current_level')
    target_level = request.form.get('target_level')

    if not name or not target_level:
        return jsonify({'code': 400, 'msg': '参数错误！'})

    try:
        current_level = int(current_level or 1)
        target_level = int(target_level)
        if not (1 <= current_level <= 5) or not (1 <= target_level <= 5):
            raise ValueError
    except ValueError:
        return jsonify({'code': 400, 'msg': '技能等级必须为1-5之间的整数！'})

    # 检查技能是否已存在
    if Skill.query.filter_by(name=name, user_id=current_user.id).first():
        return jsonify({'code': 400, 'msg': '技能已存在！'})

    new_skill = Skill(
        name=name,
        current_level=current_level,
        target_level=target_level,
        user_id=current_user.id
    )
    db.session.add(new_skill)
    db.session.commit()

    # 提交成功后，重定向回技能列表页（而不是返回 JSON）
    flash('技能添加成功', 'success')
    return redirect(url_for('skill.student_skill'))


# 添加技能学习记录（POST接口）
# ... (此路由保留 JSON 逻辑，因为它是一个 API 接口)
@skill_bp.route('/api/skill/add_record', methods=['POST'])
# ... (保持不变) ...

# 获取雷达图数据（GET接口）
@skill_bp.route('/api/skill/radar_data')
# ... (保持不变) ...

# 编辑技能（GET：渲染编辑页；POST：提交修改）
@skill_bp.route('/student/skill/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_skill(id):
    # ... (保持不变，但确保重定向使用 'skill.student_skill') ...
    if current_user.role != 0:
        flash('无权限访问！')
        return redirect(url_for('auth.dashboard'))

    skill = Skill.query.filter_by(id=id, user_id=current_user.id).first_or_404()

    if request.method == 'POST':
        name = request.form.get('skill_name')  # 注意：修改为 skill_name 以匹配前端
        current_level = request.form.get('current_level')
        target_level = request.form.get('target_level')

        if not name or not current_level or not target_level:
            flash('参数不能为空！')
            return render_template('student/edit_skill.html', skill=skill)

        # 检查技能名是否重复（排除自身）
        if Skill.query.filter(
                Skill.name == name,
                Skill.user_id == current_user.id,
                Skill.id != id
        ).first():
            flash('技能名已存在！')
            return render_template('student/edit_skill.html', skill=skill)

        skill.name = name
        skill.current_level = int(current_level)
        skill.target_level = int(target_level)
        db.session.commit()

        flash('技能修改成功！')
        return redirect(url_for('skill.student_skill'))  # ⚠️ 修正重定向目标

    # 4. GET 请求：渲染编辑页面
    return render_template('student/edit_skill.html', skill=skill)


# 删除技能
@skill_bp.route('/student/skill/delete/<int:id>', methods=['GET', 'POST'])
@login_required
def delete_skill(id):
    # ... (保持不变，但确保重定向使用 'skill.student_skill') ...
    if current_user.role != 0:
        flash('无权限执行删除操作！', 'danger')
        return redirect(url_for('auth.dashboard'))

    skill = Skill.query.filter_by(id=id, user_id=current_user.id).first()
    if not skill:
        flash('技能不存在或已被删除！', 'warning')
        return redirect(url_for('skill.student_skill'))

    SkillRecord.query.filter_by(skill_id=id, user_id=current_user.id).delete()
    db.session.delete(skill)
    db.session.commit()

    flash(f'技能「{skill.name}」已成功删除！', 'success')
    return redirect(url_for('skill.student_skill'))  # ⚠️ 修正重定向目标

# -------------------------- 保留您原有的 JSON API 接口 --------------------------
# ... (其余 JSON API 接口保持不变) ...