#!/usr/bin/env python3
"""
整合啟動器 - 同時運行Discord機器人和Flask網站
同時提供機器人和網站控制面板服務
"""

import asyncio
import logging
import threading
import time
from bot import DiscordBot
from web_app import app, set_bot_instance

def setup_logging():
    """設置日誌配置"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('system.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

def run_flask_app():
    """在單獨線程中運行Flask應用"""
    logger = logging.getLogger('web_app')
    logger.info("正在啟動Flask網站控制面板...")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

async def run_discord_bot():
    """運行Discord機器人"""
    logger = logging.getLogger('discord_bot')
    
    try:
        # 創建機器人實例
        bot = DiscordBot()
        
        # 將機器人實例傳遞給Flask應用
        set_bot_instance(bot)
        
        logger.info("正在啟動Discord機器人...")
        await bot.start_bot()
        
    except Exception as e:
        logger.error(f"Discord機器人運行錯誤: {e}")
        raise

async def main():
    """主要執行函數"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("=== ɢʀᴠ戰隊管理系統啟動 ===")
    logger.info("正在啟動整合服務...")
    
    try:
        # 在單獨線程中啟動Flask網站
        flask_thread = threading.Thread(target=run_flask_app, daemon=True)
        flask_thread.start()
        
        # 等待一下讓Flask先啟動
        await asyncio.sleep(2)
        logger.info("Flask網站控制面板已啟動 -> http://0.0.0.0:5000")
        
        # 在主線程中運行Discord機器人
        await run_discord_bot()
        
    except KeyboardInterrupt:
        logger.info("收到中斷信號，正在關閉系統...")
    except Exception as e:
        logger.error(f"系統運行錯誤: {e}")
        raise
    finally:
        logger.info("=== ɢʀᴠ戰隊管理系統已關閉 ===")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n=== 系統已停止運行 ===")
        print("感謝使用ɢʀᴠ戰隊管理系統！")