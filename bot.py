import os
import sys
import asyncio
from aiohttp import web
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant
from bs4 import BeautifulSoup
from config import Config
from database import db

bot = Client(
    "ConverterBot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN
)

# --- UTILS ---
async def check_fsub(bot, user_id):
    if not Config.FORCE_SUB_CHANNEL or Config.FORCE_SUB_CHANNEL == "0":
        return True
    try:
        await bot.get_chat_member(Config.FORCE_SUB_CHANNEL, user_id)
        return True
    except UserNotParticipant:
        return False
    except Exception:
        return True

def html_to_txt(html_content):
def html_to_txt(html_content):
    soup = BeautifulSoup(html_content, 'lxml')
    output = []
    for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li']):
        text = element.get_text(strip=True)
        if not text: continue
        
        # The 'if' below must perfectly align with the 'if' above it!
        if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            level = int(element.name.replace('h', ''))
            output.append(f"{'#' * level} {text}\n")
        elif element.name == 'li':
            output.append(f"- {text}")
        else:
            output.append(f"{text}\n")
            
    output.append(f"\n\n--- {Config.CREDIT} ---")
    return "\n".join(output)


def txt_to_html(txt_content):
    lines = txt_content.split('\n')
    body = ""
    for line in lines:
        line = line.strip()
        if not line: continue
        if line.startswith('#'):
            level = min(line.count('#'), 6)
            text = line.replace('#', '').strip()
            body += f"<h{level}>{text}</h{level}>\n"
        else:
            body += f"<p>{line}</p>\n"
            
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Converted Document</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #121212; color: #e0e0e0; line-height: 1.6; padding: 20px; max-width: 800px; margin: auto; }}
        h1, h2, h3, h4, h5, h6 {{ color: #ffffff; border-bottom: 1px solid #333; padding-bottom: 5px; }}
        p {{ font-size: 16px; margin-bottom: 15px; }}
        .footer {{ margin-top: 40px; text-align: center; font-size: 12px; color: #888; border-top: 1px solid #333; padding-top: 10px; }}
    </style>
</head>
<body>
    {body}
    <div class="footer">{Config.CREDIT}</div>
</body>
</html>"""
    return html_template

# --- HANDLERS ---
@bot.on_message(filters.private & filters.incoming)
async def pre_process(client: Client, message: Message):
    user_id = message.from_user.id
    await db.add_user(user_id)
    
    if await db.is_banned(user_id):
        await message.reply("🚫 You are banned from using this bot.")
        message.stop_propagation()

    if not await check_fsub(client, user_id):
        btn = [[InlineKeyboardButton("Join Channel", url=f"https://t.me/{Config.FORCE_SUB_CHANNEL.replace('@', '')}")]]
        await message.reply("⚠️ Please join our updates channel to use this bot.", reply_markup=InlineKeyboardMarkup(btn))
        message.stop_propagation()
    message.continue_propagation()

@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    await message.reply(f"Hello {message.from_user.first_name}!\n\nSend me an `.html` file to convert it to `.txt` with headings.\nSend me a `.txt` file to convert it to a Pro-Level Themed `.html` file.")

@bot.on_message(filters.document & filters.private)
async def handle_document(client: Client, message: Message):
    doc = message.document
    file_name = doc.file_name.lower()
    
    # 1. Forward to Dump Channel
    if Config.DUMP_CHANNEL:
        try:
            dump_msg = await message.copy(Config.DUMP_CHANNEL)
            await dump_msg.reply_text(f"👤 User: {message.from_user.mention} (`{message.from_user.id}`)")
        except Exception as e:
            print(f"Dump error: {e}")

    # 2. Log Usage
    if Config.LOG_CHANNEL:
        try:
            await client.send_message(Config.LOG_CHANNEL, f"📝 User {message.from_user.mention} requested conversion for: `{file_name}`")
        except:
            pass

    # 3. Process File
    if not (file_name.endswith('.html') or file_name.endswith('.txt')):
        return await message.reply("⚠️ Only .html and .txt files are supported.")

    msg = await message.reply("⏳ Downloading file...")
    file_path = await message.download()

    try:
        await msg.edit("⚙️ Processing file...")
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        if file_name.endswith('.html'):
            converted_data = html_to_txt(content)
            new_file_name = file_name.replace('.html', '.txt')
        else:
            converted_data = txt_to_html(content)
            new_file_name = file_name.replace('.txt', '.html')

        new_file_path = os.path.join("downloads", new_file_name)
        with open(new_file_path, "w", encoding="utf-8") as f:
            f.write(converted_data)

        await msg.edit("📤 Uploading converted file...")
        await message.reply_document(document=new_file_path, caption=f"**Converted Successfully!**\n\n©️ {Config.CREDIT}")
        
        os.remove(new_file_path)
    except Exception as e:
        await msg.edit(f"❌ Error: {e}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

# --- ADMIN COMMANDS ---
@bot.on_message(filters.command("restart") & filters.user(Config.ADMINS))
async def restart_cmd(client, message):
    await message.reply("🔄 Restarting Bot...")
    os.execl(sys.executable, sys.executable, *sys.argv)

@bot.on_message(filters.command("ban") & filters.user(Config.ADMINS))
async def ban_cmd(client, message):
    if len(message.command) > 1:
        user_id = int(message.command)
        await db.ban_user(user_id)
        await message.reply(f"✅ User {user_id} has been banned.")

@bot.on_message(filters.command("unban") & filters.user(Config.ADMINS))
async def unban_cmd(client, message):
    if len(message.command) > 1:
        user_id = int(message.command)
        await db.unban_user(user_id)
        await message.reply(f"✅ User {user_id} has been unbanned.")

@bot.on_message(filters.command("users") & filters.user(Config.ADMINS))
async def users_cmd(client, message):
    users = await db.get_all_users()
    await message.reply(f"📊 Total Users: {len(users)}")

# --- DUMMY WEB SERVER FOR PORT BINDING ---
async def web_server():
    async def handle(request):
        return web.Response(text="Bot is running!")
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', Config.PORT)
    await site.start()

async def main():
    await web_server()
    await bot.start()
    print("Bot Started!")
    await pyrogram.idle()

if __name__ == "__main__":
    import pyrogram
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
