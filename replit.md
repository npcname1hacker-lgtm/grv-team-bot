# ɢʀᴠ戰隊管理系統

## 概述

這是一個完整的Discord機器人和網站控制面板整合系統，專為ɢʀᴠ戰隊打造。系統包含：
- Discord機器人（成員管理、申請系統、指令功能）
- Flask網站控制面板（用戶管理、機器人控制、申請審核）
- PostgreSQL資料庫（用戶數據、申請記錄）
- 多層級權限管理系統

## 用戶偏好

- 溝通語言：中文（繁體）
- 界面語言：全中文
- 風格：簡單直白、易於理解

## 系統架構

### 整合架構
系統採用雙服務架構，同時運行Discord機器人和網站：

- **整合啟動器**: `integrated_launcher.py` 統一啟動所有服務
- **Discord機器人**: 在後台異步運行，處理Discord事件
- **Flask網站**: 在獨立線程運行，提供網頁控制面板
- **資料庫**: PostgreSQL (Neon) 存儲所有數據

### 核心模組

#### Discord機器人模組
- `bot.py` - 機器人核心類，處理事件和指令
- `commands.py` - 指令註冊和處理
- `application_system.py` - 申請系統功能
- `config.py` - 配置管理

#### 網站模組
- `web_app.py` - Flask應用主程序
- `web_models.py` - 網站資料庫模型（用戶、權限等）
- `web/templates/` - HTML模板（登錄、儀表板、管理頁面）
- `web/static/` - 靜態資源（CSS、JavaScript）

#### 資料庫模組
- `models.py` - 機器人資料庫模型（申請記錄等）
- `web_models.py` - 網站資料庫模型（用戶賬號、權限）

### 權限系統

三層權限架構：
1. **HIGH (隊長)** - 完整權限：
   - 創建/刪除用戶賬號
   - 修改任何用戶的密碼和權限
   - 管理機器人指令
   - 所有審核和管理功能

2. **MEDIUM (副隊長/幹部)** - 基本功能：
   - 審核申請
   - 控制機器人發送訊息
   - 查看成員信息
   - 修改自己的資料

3. **LOW (受限用戶)** - 警告狀態：
   - 無法使用任何功能
   - 需要聯繫隊長申請權限提升

### 預設管理員賬號

系統自動創建三個管理員：
- **admin0803** (隊長) - 密碼: `admin0803+0815` - HIGH權限
- **admin0815** (幹部) - 密碼: `admin-fan.wei.lun` - MEDIUM權限  
- **admin3** (幹部) - 密碼: `admin1331914` - MEDIUM權限

### 網站功能

#### 已實現功能
- ✅ 用戶登錄系統
- ✅ 儀表板（狀態概覽）
- ✅ 申請管理（查看、接受、拒絕）
- ✅ 機器人控制（讓機器人說話）
- ✅ 機器人狀態監控
- ✅ 用戶管理（隊長專用）
- ✅ 個人設置（修改資料、密碼）
- ✅ 權限管理（隊長可調整用戶權限）

#### 計劃中功能
- ⏳ 電子郵件驗證系統
- ⏳ 電話驗證系統（SMS）
- ⏳ 忘記密碼功能
- ⏳ 自定義機器人指令（隊長專用）
- ⏳ 伺服器成員管理（禁言、踢人等）

### 電子郵件功能計劃

**注意**: 用戶選擇不使用Replit的SendGrid集成。
如需實現電子郵件功能，可選方案：
1. 手動設置SendGrid API密鑰
2. 使用Mailgun服務
3. 使用Gmail SMTP
4. 使用Amazon SES

暫時跳過電子郵件功能，專注核心管理功能。

## 技術棧

### 後端
- **Flask** - 網站框架
- **Flask-Login** - 用戶認證
- **SQLAlchemy** - ORM資料庫
- **discord.py** - Discord API
- **bcrypt** - 密碼加密
- **PostgreSQL** - 資料庫

### 前端
- **Bootstrap 5** - UI框架
- **Font Awesome** - 圖標
- **原生JavaScript** - 互動功能

### 部署
- **Replit** - 雲端運行環境
- **Neon PostgreSQL** - 託管資料庫

## 啟動方式

系統通過 `integrated_launcher.py` 統一啟動：
- 先啟動Flask網站（端口5000）
- 然後啟動Discord機器人
- 如果機器人連接失敗，網站仍可正常使用

訪問: http://0.0.0.0:5000

## 環境變數

必需的環境變數：
- `DATABASE_URL` - PostgreSQL連接字串
- `DISCORD_TOKEN` - Discord機器人令牌
- `FLASK_SECRET_KEY` - Flask會話密鑰（可選）

可選的環境變數（用於擴展功能）：
- `SENDGRID_API_KEY` - 電子郵件服務
- `TWILIO_*` - SMS服務

## 最近變更

### 2025-10-18
- ✅ 創建完整的Flask網站控制面板
- ✅ 實現用戶認證和權限系統
- ✅ 整合Discord機器人和網站
- ✅ 添加機器人控制API
- ✅ 實現申請管理界面
- ✅ 創建用戶管理功能（隊長專用）
- ✅ 修復資料庫連接問題
- ✅ 改進啟動器，即使機器人離線網站也能運行

## 項目文件結構

```
.
├── integrated_launcher.py  # 整合啟動器
├── bot.py                  # Discord機器人核心
├── web_app.py             # Flask網站應用
├── web_models.py          # 網站資料庫模型
├── models.py              # 機器人資料庫模型
├── commands.py            # Discord指令
├── application_system.py  # 申請系統
├── config.py              # 配置管理
└── web/
    ├── templates/         # HTML模板
    │   ├── base.html
    │   ├── login.html
    │   ├── dashboard.html
    │   ├── applications.html
    │   ├── bot_control.html
    │   ├── users.html
    │   ├── settings.html
    │   └── restricted.html
    └── static/            # 靜態資源
        ├── css/
        │   └── style.css
        └── js/
            └── main.js
```

## 版本資訊

- **當前版本**: V1.00.8
- **創作者**: ɢʀᴠ戰隊隊長殤嵐
- **最後更新**: 2025-10-18