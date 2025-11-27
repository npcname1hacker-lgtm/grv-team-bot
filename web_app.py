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
from datetime import datetime, timedelta
import random
import string
from web_models import WebUser, UserRole, BotCommand, get_web_database, PasswordReset
from models import get_bot_database
from email_service import get_email_service

app = Flask(__name__, template_folder='web/templates', static_folder='web/static')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your-secret-key-here')

# Flask-Login設置
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = '請先登錄以訪問此頁面'

# 延遲初始化的資料庫管理器
def get_databases():
    """獲取資料庫管理器實例"""
    return get_web_database(), get_bot_database()

@login_manager.user_loader
def load_user(user_id):
    web_db, _ = get_databases()
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
        
        web_db, _ = get_databases()
        user = web_db.get_user_by_username(username)
        
        if user and user.check_password(password):
            # 更新最後登錄時間
            web_db, _ = get_databases()
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
            web_db, _ = get_databases()
            session = web_db.get_session()
            try:
                existing_email = session.query(WebUser).filter_by(email=email).first()
                if existing_email:
                    return jsonify({'success': False, 'error': '此電子郵件已被註冊'})
            finally:
                session.close()
            
            # 發送驗證碼
            email_svc = get_email_service()
            success, message = email_svc.send_verification_email(email, '註冊新帳號')
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
        email_svc = get_email_service()
        code_valid, message = email_svc.verify_code(email, verification_code)
        if not code_valid:
            flash(f'驗證碼錯誤：{message}', 'error')
            return render_template('register.html')
        
        # 檢查用戶名是否已存在
        web_db, _ = get_databases()
        existing_user = web_db.get_user_by_username(username)
        if existing_user:
            flash('用戶名已被使用，請選擇其他用戶名', 'error')
            return render_template('register.html')
        
        # 創建新用戶（預設為LOW權限，需要隊長審核）
        try:
            web_db, _ = get_databases()
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
    _, bot_db = get_databases()
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
    
    _, bot_db = get_databases()
    applications = bot_db.get_pending_applications()
    return render_template('applications.html', applications=applications)

@app.route('/api/application/<int:app_id>/approve', methods=['POST'])
@login_required
def approve_application(app_id):
    """接受申請API"""
    if current_user.role == UserRole.LOW:
        return jsonify({'error': '權限不足'}), 403
    
    _, bot_db = get_databases()
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
    _, bot_db = get_databases()
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
    web_db, _ = get_databases()
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
    web_db, _ = get_databases()
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
    
    web_db, _ = get_databases()
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
        web_db, _ = get_databases()
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
    
    web_db, _ = get_databases()
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
    
    web_db, _ = get_databases()
    success = web_db.update_user_role(user_id, new_role)
    if success:
        return jsonify({'success': True, 'message': '權限已更新'})
    else:
        return jsonify({'error': '更新失敗'}), 400

@app.route('/api/user/unlink-discord', methods=['POST'])
@login_required
def unlink_discord():
    """解除 Discord 綁定"""
    web_db, _ = get_databases()
    session = web_db.get_session()
    try:
        user = session.query(WebUser).filter_by(id=current_user.id).first()
        if user:
            user.discord_id = None
            session.commit()
            return jsonify({'success': True, 'message': 'Discord 綁定已解除'})
        return jsonify({'error': '用戶不存在'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        session.close()

@app.route('/api/user/link-discord', methods=['POST'])
@login_required
def link_discord():
    """綁定 Discord ID - 僅隊長可用"""
    if current_user.role != UserRole.HIGH:
        return jsonify({'error': '僅隊長可綁定 Discord 帳號'}), 403
    
    data = request.json
    discord_id = data.get('discord_id')
    
    if not discord_id:
        return jsonify({'error': '缺少 Discord ID'}), 400
    
    web_db, _ = get_databases()
    session = web_db.get_session()
    try:
        user = session.query(WebUser).filter_by(id=current_user.id).first()
        if user:
            user.discord_id = discord_id
            session.commit()
            return jsonify({'success': True, 'message': 'Discord 帳號已綁定'})
        return jsonify({'error': '用戶不存在'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        session.close()

@app.route('/forgot-password')
def forgot_password_page():
    """忘記密碼重置頁面"""
    username = request.args.get('username')
    if not username:
        return redirect(url_for('login'))
    return render_template('forgot_password.html', username=username)

@app.route('/api/forgot-password', methods=['POST'])
def forgot_password():
    """生成密碼重置驗證碼"""
    data = request.json
    username = data.get('username', '').strip()
    
    if not username:
        return jsonify({'error': '請輸入用戶名'}), 400
    
    web_db, _ = get_databases()
    
    # 檢查用戶是否存在
    user = web_db.get_user_by_username(username)
    if not user:
        return jsonify({'error': '用戶不存在'}), 404
    
    # 生成 6 位驗證碼
    code = ''.join(random.choices(string.digits, k=6))
    
    # 保存驗證碼到資料庫（10分鐘有效期）
    expires_at = datetime.utcnow() + timedelta(minutes=10)
    reset_id = web_db.create_password_reset(username, code, expires_at)
    
    print(f"\n{'='*60}")
    print(f"忘記密碼驗證碼已創建")
    print(f"{'='*60}")
    print(f"用戶名: {username}")
    print(f"驗證碼: {code}")
    print(f"有效期: 10 分鐘")
    print(f"記錄 ID: {reset_id}")
    print(f"{'='*60}\n")
    
    # 非同步發送 DM 給隊長
    if discord_bot_instance and hasattr(discord_bot_instance, 'bot'):
        try:
            # 使用 threading 在後台發送
            def send_dm_background():
                try:
                    bot_instance = discord_bot_instance.bot
                    if bot_instance and hasattr(bot_instance, 'loop'):
                        asyncio.run_coroutine_threadsafe(
                            send_forgot_password_notification(code, username),
                            bot_instance.loop
                        )
                    else:
                        print(f"✗ 機器人 loop 不可用")
                except Exception as e:
                    print(f"✗ 後台發送 DM 失敗: {e}")
            
            thread = threading.Thread(target=send_dm_background, daemon=True)
            thread.start()
        except Exception as e:
            print(f"✗ 啟動後台線程失敗: {e}")
    
    return jsonify({'success': True, 'message': '驗證碼已發送'})

@app.route('/api/reset-password', methods=['POST'])
def reset_password():
    """重置密碼"""
    data = request.json
    username = data.get('username', '').strip()
    code = data.get('code', '').strip()
    new_password = data.get('new_password', '')
    
    if not username or not code or not new_password:
        return jsonify({'error': '缺少必要信息'}), 400
    
    if len(code) != 6 or not code.isdigit():
        return jsonify({'error': '驗證碼格式不正確'}), 400
    
    if len(new_password) < 6:
        return jsonify({'error': '密碼至少 6 個字符'}), 400
    
    web_db, _ = get_databases()
    
    # 驗證碼
    reset_record = web_db.verify_reset_code(username, code)
    if not reset_record:
        return jsonify({'error': '驗證碼無效或已過期'}), 400
    
    # 更新密碼
    user = web_db.get_user_by_username(username)
    if not user:
        return jsonify({'error': '用戶不存在'}), 404
    
    user_id = user.id
    success = web_db.change_user_password(user_id, new_password)
    
    if success:
        # 標記驗證碼為已使用
        web_db.mark_reset_as_used(reset_record.id)
        
        # 發送確認 DM 給隊長
        if discord_bot_instance and hasattr(discord_bot_instance, 'bot'):
            try:
                bot_instance = discord_bot_instance.bot
                if bot_instance and hasattr(bot_instance, 'loop'):
                    asyncio.run_coroutine_threadsafe(
                        send_password_reset_confirmation(username),
                        bot_instance.loop
                    )
            except Exception as e:
                print(f"發送確認通知失敗: {e}")
        
        return jsonify({'success': True, 'message': '密碼已重置'})
    else:
        return jsonify({'error': '重置失敗，請稍後重試'}), 400

async def send_forgot_password_notification(code, username):
    """發送忘記密碼通知到隊長 DM"""
    try:
        # 台灣時區時間
        from datetime import timezone, timedelta
        tz = timezone(timedelta(hours=8))
        current_time = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
        
        # 構建消息
        message = f"""忘記密碼⚠️
用戶名：{username}
時間：{current_time}（台灣時間）
驗證碼：{code}

請不要把驗證碼給任何人！"""
        
        # 嘗試獲取隊長
        web_db, _ = get_databases()
        admins = web_db.get_admin_users()
        
        if not admins:
            print(f"✗ 未找到隊長")
            print(f"\n{message}\n")
            return
        
        admin = admins[0]
        if not admin.discord_id:
            print(f"✗ 隊長未綁定 Discord ID")
            print(f"\n{message}\n")
            return
        
        # 嘗試發送 Discord DM
        try:
            admin_discord_id = int(admin.discord_id)
            # 訪問機器人實例的 bot 屬性
            bot = discord_bot_instance.bot if hasattr(discord_bot_instance, 'bot') else discord_bot_instance
            user = await bot.fetch_user(admin_discord_id)
            await user.send(message)
            print(f"\n✓ 已發送 Discord DM 給隊長")
            print(f"  隊長 ID: {admin_discord_id}")
            print(f"  用戶名: {username}")
            print(f"  驗證碼: {code}\n")
        except Exception as e:
            print(f"\n✗ Discord DM 發送失敗: {str(e)[:100]}")
            print(f"  原始訊息:")
            print(message)
            print()
        
    except Exception as e:
        print(f"✗ 通知系統錯誤: {str(e)[:100]}")

async def send_password_reset_confirmation(username):
    """發送密碼重置成功確認"""
    try:
        web_db, _ = get_databases()
        admins = web_db.get_admin_users()
        
        if not admins or not admins[0].discord_id:
            return
        
        try:
            admin_discord_id = int(admins[0].discord_id)
            user = await discord_bot_instance.fetch_user(admin_discord_id)
        except:
            return
        
        message = f"""✅ 密碼重置通知
用戶 {username} 已成功重置密碼。
請提醒用戶妥善保管密碼，不要給別人。"""
        
        await user.send(message)
    except Exception as e:
        print(f"發送確認通知失敗: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)