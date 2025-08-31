"""
Discord Bot - 指令處理模組
包含所有機器人指令的實現
"""

import discord
from discord.ext import commands
import asyncio
import random
import time
import logging

def setup_commands(bot):
    """設置所有機器人指令"""
    
    @bot.command(name='hello', aliases=['hi', '你好'])
    async def hello_command(ctx):
        """打招呼指令"""
        greetings = [
            f"👋 Hello {ctx.author.mention}！",
            f"🎉 嗨！{ctx.author.display_name}",
            f"✨ 哈囉 {ctx.author.mention}！很高興見到你！",
            f"🌟 Hi there, {ctx.author.display_name}！"
        ]
        
        embed = discord.Embed(
            title=random.choice(greetings),
            description="我是一個友善的Discord機器人！ 😊",
            color=0x00ff00
        )
        embed.set_thumbnail(url=ctx.author.avatar.url if ctx.author.avatar else None)
        await ctx.send(embed=embed)
    
    @bot.command(name='ping')
    async def ping_command(ctx):
        """檢查機器人延遲"""
        start_time = time.time()
        message = await ctx.send("🏓 Pinging...")
        end_time = time.time()
        
        # 計算延遲
        latency = round(bot.latency * 1000)  # WebSocket延遲
        response_time = round((end_time - start_time) * 1000)  # 回應時間
        
        embed = discord.Embed(title="🏓 Pong!", color=0x00ff00)
        embed.add_field(name="WebSocket延遲", value=f"{latency}ms", inline=True)
        embed.add_field(name="回應時間", value=f"{response_time}ms", inline=True)
        
        # 根據延遲設置顏色
        if latency < 100:
            embed.color = 0x00ff00  # 綠色 - 很好
        elif latency < 200:
            embed.color = 0xffff00  # 黃色 - 普通
        else:
            embed.color = 0xff0000  # 紅色 - 較差
        
        await message.edit(content="", embed=embed)
    
    @bot.command(name='info', aliases=['about', 'botinfo'])
    async def info_command(ctx):
        """顯示機器人資訊"""
        embed = discord.Embed(
            title="🤖 機器人資訊",
            description="一個用Python編寫的Discord機器人",
            color=0x0099ff
        )
        
        # 基本資訊
        embed.add_field(name="機器人名稱", value=bot.user.name, inline=True)
        embed.add_field(name="機器人ID", value=bot.user.id, inline=True)
        embed.add_field(name="伺服器數量", value=len(bot.guilds), inline=True)
        
        # 統計資訊
        total_members = sum(guild.member_count for guild in bot.guilds)
        embed.add_field(name="總用戶數", value=total_members, inline=True)
        embed.add_field(name="頻道數", value=len(list(bot.get_all_channels())), inline=True)
        embed.add_field(name="延遲", value=f"{round(bot.latency * 1000)}ms", inline=True)
        
        # 技術資訊
        embed.add_field(name="Python版本", value="3.8+", inline=True)
        embed.add_field(name="discord.py版本", value=discord.__version__, inline=True)
        embed.add_field(name="指令前綴", value="`!`", inline=True)
        
        embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else None)
        embed.set_footer(text=f"請求者: {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        
        await ctx.send(embed=embed)
    
    @bot.command(name='serverinfo', aliases=['server', 'guildinfo'])
    async def serverinfo_command(ctx):
        """顯示伺服器資訊"""
        guild = ctx.guild
        
        embed = discord.Embed(
            title=f"🏰 {guild.name} 伺服器資訊",
            color=0x9932cc
        )
        
        # 基本資訊
        embed.add_field(name="伺服器名稱", value=guild.name, inline=True)
        embed.add_field(name="伺服器ID", value=guild.id, inline=True)
        embed.add_field(name="擁有者", value=guild.owner.mention if guild.owner else "未知", inline=True)
        
        # 統計資訊
        embed.add_field(name="成員數量", value=guild.member_count, inline=True)
        embed.add_field(name="頻道數量", value=len(guild.channels), inline=True)
        embed.add_field(name="角色數量", value=len(guild.roles), inline=True)
        
        # 其他資訊
        embed.add_field(name="創建時間", value=guild.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        embed.add_field(name="驗證等級", value=str(guild.verification_level).title(), inline=True)
        embed.add_field(name="加速等級", value=guild.premium_tier, inline=True)
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        embed.set_footer(text=f"請求者: {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        
        await ctx.send(embed=embed)
    
    @bot.command(name='userinfo', aliases=['user', 'member'])
    async def userinfo_command(ctx, member: discord.Member = None):
        """顯示用戶資訊"""
        if member is None:
            member = ctx.author
        
        embed = discord.Embed(
            title=f"👤 {member.display_name} 的資訊",
            color=member.color if member.color != discord.Color.default() else 0x0099ff
        )
        
        # 基本資訊
        embed.add_field(name="用戶名稱", value=f"{member.name}#{member.discriminator}", inline=True)
        embed.add_field(name="顯示名稱", value=member.display_name, inline=True)
        embed.add_field(name="用戶ID", value=member.id, inline=True)
        
        # 時間資訊
        embed.add_field(name="帳號創建", value=member.created_at.strftime("%Y-%m-%d"), inline=True)
        embed.add_field(name="加入伺服器", value=member.joined_at.strftime("%Y-%m-%d") if member.joined_at else "未知", inline=True)
        embed.add_field(name="狀態", value=str(member.status).title(), inline=True)
        
        # 角色資訊
        roles = [role.mention for role in member.roles[1:]]  # 排除@everyone角色
        if roles:
            embed.add_field(name=f"角色 ({len(roles)})", value=" ".join(roles), inline=False)
        
        embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
        embed.set_footer(text=f"請求者: {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        
        await ctx.send(embed=embed)
    
    @bot.command(name='say', aliases=['echo'])
    async def say_command(ctx, *, message):
        """讓機器人說話"""
        # 刪除原始指令訊息
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass
        
        # 檢查訊息長度
        if len(message) > 2000:
            embed = discord.Embed(
                title="❌ 訊息太長",
                description="訊息不能超過2000個字符。",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            return
        
        # 發送訊息
        await ctx.send(message)
    
    @bot.command(name='clear', aliases=['purge', 'clean'])
    @commands.has_permissions(manage_messages=True)
    async def clear_command(ctx, amount: int = 5):
        """清除訊息（需要管理訊息權限）"""
        if amount < 1:
            embed = discord.Embed(
                title="❌ 無效數量",
                description="清除數量必須大於0。",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            return
        
        if amount > 100:
            embed = discord.Embed(
                title="❌ 數量太大",
                description="一次最多只能清除100條訊息。",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            return
        
        try:
            deleted = await ctx.channel.purge(limit=amount + 1)  # +1 包含指令本身
            
            embed = discord.Embed(
                title="✅ 清除完成",
                description=f"已清除 {len(deleted) - 1} 條訊息。",
                color=0x00ff00
            )
            
            # 發送確認訊息並在3秒後刪除
            confirmation = await ctx.send(embed=embed)
            await asyncio.sleep(3)
            await confirmation.delete()
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ 權限不足",
                description="機器人沒有刪除訊息的權限。",
                color=0xff0000
            )
            await ctx.send(embed=embed)
    
    @bot.command(name='help')
    async def help_command(ctx, command_name=None):
        """顯示幫助資訊"""
        if command_name:
            # 顯示特定指令的幫助
            command = bot.get_command(command_name)
            if command:
                embed = discord.Embed(
                    title=f"📖 指令: {command.name}",
                    description=command.help or "沒有描述",
                    color=0x0099ff
                )
                
                # 別名
                if command.aliases:
                    embed.add_field(name="別名", value=", ".join(command.aliases), inline=False)
                
                # 用法
                embed.add_field(name="用法", value=f"`!{command.name} {command.signature}`", inline=False)
                
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="❌ 找不到指令",
                    description=f"指令 `{command_name}` 不存在。",
                    color=0xff0000
                )
                await ctx.send(embed=embed)
        else:
            # 顯示所有指令
            embed = discord.Embed(
                title="📚 指令列表",
                description="以下是所有可用的指令：",
                color=0x0099ff
            )
            
            # 基本指令
            basic_commands = [
                "`!hello` - 打招呼",
                "`!ping` - 檢查延遲",
                "`!info` - 機器人資訊",
                "`!help [指令]` - 顯示幫助"
            ]
            embed.add_field(name="🎯 基本指令", value="\n".join(basic_commands), inline=False)
            
            # 資訊指令
            info_commands = [
                "`!serverinfo` - 伺服器資訊",
                "`!userinfo [用戶]` - 用戶資訊"
            ]
            embed.add_field(name="ℹ️ 資訊指令", value="\n".join(info_commands), inline=False)
            
            # 實用指令
            utility_commands = [
                "`!say <訊息>` - 讓機器人說話",
                "`!clear [數量]` - 清除訊息 (需要權限)"
            ]
            embed.add_field(name="🔧 實用指令", value="\n".join(utility_commands), inline=False)
            
            embed.set_footer(text="使用 !help <指令名稱> 獲取特定指令的詳細資訊")
            
            await ctx.send(embed=embed)
