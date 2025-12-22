from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from models import db, Course

course_bp = Blueprint('course', __name__)


# 学生课程管理页
@course_bp.route('/student/course')
@login_required
def student_course():
    if current_user.role != 0:
        flash('无权限访问！')
        return redirect(url_for('auth.dashboard'))

    courses = Course.query.filter_by(user_id=current_user.id).all()
    # 计算总GPA（可选）
    total_credits = sum(course.credit for course in courses)
    total_gpa = sum(
        course.credit * course.grade_point for course in courses) / total_credits if total_credits > 0 else 0

    return render_template('student/course.html', courses=courses, total_gpa=round(total_gpa, 2))


# 添加课程（POST接口）
@course_bp.route('/api/course/add', methods=['POST'])
@login_required
def add_course():
    if current_user.role != 0:
        return jsonify({'code': 403, 'msg': '无权限！'})

    data = request.get_json()
    if not data.get('name') or not data.get('credit'):
        return jsonify({'code': 400, 'msg': '参数错误！'})

    # 检查课程是否已存在
    if Course.query.filter_by(name=data['name'], user_id=current_user.id).first():
        return jsonify({'code': 400, 'msg': '课程已存在！'})

    new_course = Course(
        name=data['name'],
        credit=float(data['credit']),
        score=float(data.get('score', 0)),
        user_id=current_user.id
    )
    db.session.add(new_course)
    db.session.commit()

    return jsonify({'code': 200, 'msg': '课程添加成功！'})


# 更新课程成绩（POST接口）
@course_bp.route('/api/course/update_score', methods=['POST'])
@login_required
def update_score():
    if current_user.role != 0:
        return jsonify({'code': 403, 'msg': '无权限！'})

    data = request.get_json()
    course_id = data.get('course_id')
    score = float(data.get('score', 0))

    course = Course.query.get(course_id)
    if not course or course.user_id != current_user.id:
        return jsonify({'code': 404, 'msg': '课程不存在！'})

    course.score = score
    db.session.commit()

    return jsonify({'code': 200, 'msg': '成绩更新成功！'})


# 删除课程（GET接口）
@course_bp.route('/api/course/delete/<int:course_id>')
@login_required
def delete_course(course_id):
    if current_user.role != 0:
        return jsonify({'code': 403, 'msg': '无权限！'})

    course = Course.query.get(course_id)
    if not course or course.user_id != current_user.id:
        return jsonify({'code': 404, 'msg': '课程不存在！'})

    db.session.delete(course)
    db.session.commit()

    return jsonify({'code': 200, 'msg': '课程删除成功！'})