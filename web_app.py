"""
戰隊管理網站 - Flask後端應用
提供完整的Discord機器人控制面板
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session as flask_session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import discord
import asyncio
import threading
import logging
import os
import json
from datetime import datetime
from web_models import WebDatabaseManager, WebUser, UserRole, BotCommand
from models import DatabaseManager, TeamApplication
from email_service import email_service

app = Flask(__name__, template_folder='web/templates', static_folder='web/static')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your-secret-key-here')

# Flask-Login設置
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = '請先登錄以訪問此頁面'

# 資料庫管理器
web_db = WebDatabaseManager()
bot_db = DatabaseManager()

@login_manager.user_loader
def load_user(user_id):
    return web_db.get_user_by_id(int(user_id))

# 權限裝飾器
def require_role(required_role):
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('login'))
            
            if current_user.role == UserRole.LOW:
                flash('你的權限不夠，請去私信隊長來申請', 'error')
                return redirect(url_for('dashboard'))
            
            if required_role == UserRole.HIGH and current_user.role != UserRole.HIGH:
                flash('僅隊長可使用此功能', 'error')
                return redirect(url_for('dashboard'))
            
            return func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator

# 獲取機器人實例的全局變數
discord_bot_instance = None

def set_bot_instance(bot):
    """設置機器人實例以供網站使用"""
    global discord_bot_instance
    discord_bot_instance = bot

@app.route('/')
def index():
    """首頁"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """登錄頁面"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = web_db.get_user_by_username(username)
        
        if user and user.check_password(password):
            # 更新最後登錄時間
            session = web_db.get_session()
            try:
                user.last_login = datetime.utcnow()
                session.merge(user)
                session.commit()
            finally:
                session.close()
            
            login_user(user)
            flash(f'歡迎回來，{user.username}！', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('用戶名或密碼錯誤', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """註冊頁面 - 使用電子郵件驗證碼註冊"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        # 步驟1: 發送驗證碼
        if action == 'send_code':
            email = request.form.get('email')
            
            # 檢查郵箱是否已被使用
            session = web_db.get_session()
            try:
                existing_email = session.query(WebUser).filter_by(email=email).first()
                if existing_email:
                    return jsonify({'success': False, 'error': '此電子郵件已被註冊'})
            finally:
                session.close()
            
            # 發送驗證碼
            success, message = email_service.send_verification_email(email, '註冊新帳號')
            return jsonify({'success': success, 'message': message})
        
        # 步驟2: 完成註冊
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        verification_code = request.form['verification_code']
        discord_id = request.form.get('discord_id', '')
        
        # 驗證密碼
        if password != confirm_password:
            flash('兩次輸入的密碼不一致', 'error')
            return render_template('register.html')
        
        # 驗證驗證碼
        code_valid, message = email_service.verify_code(email, verification_code)
        if not code_valid:
            flash(f'驗證碼錯誤：{message}', 'error')
            return render_template('register.html')
        
        # 檢查用戶名是否已存在
        existing_user = web_db.get_user_by_username(username)
        if existing_user:
            flash('用戶名已被使用，請選擇其他用戶名', 'error')
            return render_template('register.html')
        
        # 創建新用戶（預設為LOW權限，需要隊長審核）
        try:
            user_id = web_db.create_user(
                username=username,
                password=password,
                role=UserRole.LOW,  # 新用戶預設受限，需要隊長提升權限
                created_by='self_register',
                email=email
            )
            
            # 如果提供了Discord ID，更新它
            if discord_id:
                session = web_db.get_session()
                try:
                    user = session.query(WebUser).filter_by(id=user_id).first()
                    if user:
                        user.discord_id = discord_id
                        session.commit()
                finally:
                    session.close()
            
            flash('註冊成功！您的帳號需要隊長審核後才能使用完整功能。請聯繫隊長申請權限提升。', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            flash(f'註冊失敗：{str(e)}', 'error')
            return render_template('register.html')
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    """登出"""
    logout_user()
    flash('已成功登出', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """儀表板"""
    if current_user.role == UserRole.LOW:
        flash('你的權限不夠，請去私信隊長來申請', 'error')
        return render_template('restricted.html')
    
    # 獲取基本統計
    pending_applications = len(bot_db.get_pending_applications())
    
    # 獲取機器人狀態
    bot_status = {
        'online': discord_bot_instance is not None and hasattr(discord_bot_instance, 'bot') and not discord_bot_instance.bot.is_closed() if discord_bot_instance else False,
        'guild_count': len(discord_bot_instance.bot.guilds) if discord_bot_instance and hasattr(discord_bot_instance, 'bot') and discord_bot_instance.bot.guilds else 0,
        'member_count': sum(guild.member_count for guild in discord_bot_instance.bot.guilds) if discord_bot_instance and hasattr(discord_bot_instance, 'bot') and discord_bot_instance.bot.guilds else 0
    }
    
    return render_template('dashboard.html', 
                         pending_applications=pending_applications,
                         bot_status=bot_status)

@app.route('/applications')
@login_required
def applications():
    """申請管理頁面"""
    if current_user.role == UserRole.LOW:
        flash('你的權限不夠，請去私信隊長來申請', 'error')
        return redirect(url_for('dashboard'))
    
    applications = bot_db.get_pending_applications()
    return render_template('applications.html', applications=applications)

@app.route('/api/application/<int:app_id>/approve', methods=['POST'])
@login_required
def approve_application(app_id):
    """接受申請API"""
    if current_user.role == UserRole.LOW:
        return jsonify({'error': '權限不足'}), 403
    
    success = bot_db.update_application_status(app_id, 'approved', str(current_user.id))
    
    if success:
        # 這裡需要通知Discord機器人發送歡迎訊息
        return jsonify({'success': True, 'message': '申請已接受'})
    else:
        return jsonify({'error': '操作失敗'}), 400

@app.route('/api/application/<int:app_id>/reject', methods=['POST'])
@login_required
def reject_application(app_id):
    """拒絕申請API"""
    if current_user.role == UserRole.LOW:
        return jsonify({'error': '權限不足'}), 403
    
    reason = request.json.get('reason', '未提供原因')
    success = bot_db.update_application_status(app_id, 'rejected', str(current_user.id), reason)
    
    if success:
        return jsonify({'success': True, 'message': '申請已拒絕'})
    else:
        return jsonify({'error': '操作失敗'}), 400

@app.route('/users')
@login_required
@require_role(UserRole.HIGH)
def users():
    """用戶管理頁面（隊長專用）"""
    all_users = web_db.get_all_users()
    return render_template('users.html', users=all_users)

@app.route('/bot-control')
@login_required
def bot_control():
    """機器人控制頁面"""
    if current_user.role == UserRole.LOW:
        flash('你的權限不夠，請去私信隊長來申請', 'error')
        return redirect(url_for('dashboard'))
    
    return render_template('bot_control.html')

@app.route('/api/bot/status')
@login_required
def bot_status():
    """獲取機器人狀態API"""
    if not discord_bot_instance or not hasattr(discord_bot_instance, 'bot'):
        return jsonify({
            'online': False,
            'latency': 0,
            'guild_count': 0,
            'member_count': 0
        })
    
    return jsonify({
        'online': not discord_bot_instance.bot.is_closed(),
        'latency': round(discord_bot_instance.bot.latency * 1000),
        'guild_count': len(discord_bot_instance.bot.guilds),
        'member_count': sum(guild.member_count for guild in discord_bot_instance.bot.guilds)
    })

@app.route('/api/bot/channels')
@login_required
def bot_channels():
    """獲取機器人可訪問的頻道列表"""
    if current_user.role == UserRole.LOW:
        return jsonify({'error': '權限不足'}), 403
    
    if not discord_bot_instance or not hasattr(discord_bot_instance, 'bot') or discord_bot_instance.bot.is_closed():
        return jsonify({'error': '機器人未連接'}), 503
    
    channels = []
    for guild in discord_bot_instance.bot.guilds:
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                channels.append({
                    'id': str(channel.id),
                    'name': f'#{channel.name}',
                    'guild_name': guild.name
                })
    
    return jsonify({'channels': channels})

@app.route('/api/bot/say', methods=['POST'])
@login_required
def bot_say():
    """讓機器人說話API"""
    if current_user.role == UserRole.LOW:
        return jsonify({'error': '權限不足'}), 403
    
    message = request.json.get('message')
    channel_id = request.json.get('channel_id')
    
    if not message:
        return jsonify({'error': '消息不能為空'}), 400
    
    if not discord_bot_instance or not hasattr(discord_bot_instance, 'bot') or discord_bot_instance.bot.is_closed():
        return jsonify({'error': '機器人未連接'}), 503
    
    # 在機器人線程中執行發送消息
    async def send_message():
        try:
            channel = discord_bot_instance.bot.get_channel(int(channel_id))
            if not channel:
                return False, '找不到指定頻道'
            
            await channel.send(message)
            return True, '消息已發送'
        except Exception as e:
            return False, str(e)
    
    # 使用asyncio在機器人的事件循環中執行
    try:
        loop = discord_bot_instance.bot.loop
        future = asyncio.run_coroutine_threadsafe(send_message(), loop)
        success, msg = future.result(timeout=10)
        
        if success:
            return jsonify({'success': True, 'message': msg})
        else:
            return jsonify({'error': msg}), 400
    except Exception as e:
        return jsonify({'error': f'發送失敗: {str(e)}'}), 500

@app.route('/settings')
@login_required
def settings():
    """設置頁面"""
    return render_template('settings.html', user=current_user)

@app.route('/api/user/update', methods=['POST'])
@login_required 
def update_user_profile():
    """更新用戶資料API"""
    data = request.json
    session = web_db.get_session()
    
    try:
        user = session.query(WebUser).filter_by(id=current_user.id).first()
        if user:
            if 'email' in data:
                user.email = data['email']
            if 'phone' in data:
                user.phone = data['phone']
            session.commit()
            return jsonify({'success': True, 'message': '資料已更新'})
        return jsonify({'error': '用戶不存在'}), 404
    finally:
        session.close()

@app.route('/api/user/change-password', methods=['POST'])
@login_required
def change_password():
    """更改密碼API"""
    data = request.json
    old_password = data.get('old_password')
    new_password = data.get('new_password')
    
    if not current_user.check_password(old_password):
        return jsonify({'error': '原密碼錯誤'}), 400
    
    success = web_db.change_user_password(current_user.id, new_password)
    if success:
        return jsonify({'success': True, 'message': '密碼已更新'})
    else:
        return jsonify({'error': '更新失敗'}), 400

@app.route('/api/admin/create-user', methods=['POST'])
@login_required
@require_role(UserRole.HIGH)
def create_user():
    """創建新用戶API（隊長專用）"""
    data = request.json
    username = data.get('username')
    password = data.get('password') 
    role = UserRole(data.get('role', 'medium'))
    
    try:
        user_id = web_db.create_user(
            username=username,
            password=password,
            role=role,
            created_by=current_user.username
        )
        return jsonify({'success': True, 'message': f'用戶 {username} 已創建', 'user_id': user_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/admin/change-user-password', methods=['POST'])
@login_required
@require_role(UserRole.HIGH)
def admin_change_password():
    """管理員更改任意用戶密碼API"""
    data = request.json
    user_id = data.get('user_id')
    new_password = data.get('new_password')
    
    success = web_db.change_user_password(user_id, new_password)
    if success:
        return jsonify({'success': True, 'message': '密碼已更新'})
    else:
        return jsonify({'error': '更新失敗'}), 400

@app.route('/api/admin/update-user-role', methods=['POST'])
@login_required
@require_role(UserRole.HIGH)
def update_user_role():
    """更新用戶權限API（隊長專用）"""
    data = request.json
    user_id = data.get('user_id')
    new_role = UserRole(data.get('role'))
    
    success = web_db.update_user_role(user_id, new_role)
    if success:
        return jsonify({'success': True, 'message': '權限已更新'})
    else:
        return jsonify({'error': '更新失敗'}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)