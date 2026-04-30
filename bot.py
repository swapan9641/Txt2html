import os
import sys
import asyncio
import re
from aiohttp import web
from pyrogram import Client, filters, idle
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
    soup = BeautifulSoup(html_content, 'lxml')
    output = []
    
    for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'a', 'p']):
        if element.name.startswith('h'):
            level = int(element.name.replace('h', ''))
            text = element.get_text(strip=True)
            if text:
                output.append(f"\n{'#' * level} {text}\n")
                
        elif element.name == 'a':
            text = element.get_text(strip=True)
            url = ""
            
            onclick = element.get('onclick', '')
            if "playVideo" in onclick:
                # Extracts URL perfectly even if there are extra parameters
                match = re.search(r"playVideo\('([^']+)'", onclick)
                if match:
                    url = match.group(1)
            
            if not url:
                href = element.get('href', '')
                if href and href != '#':
                    url = href
                    
            if text and url:
                output.append(f"{text}:{url}")
                
        elif element.name == 'p':
            text = element.get_text(strip=True)
            if text and "onclick" not in str(element):
                output.append(f"{text}")

    output.append(f"\n\n--- {Config.CREDIT} ---")
    return "\n".join(output)

def txt_to_html(txt_content):
    lines = txt_content.split('\n')
    playlist_html = ""
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        if line.startswith('#'):
            text = line.replace('#', '').strip()
            playlist_html += f'<div class="topic-heading">{text}</div>\n'
            
        elif "http" in line:
            split_idx = line.find('http')
            title = line[:split_idx].strip(': ')
            url = line[split_idx:].strip()
            if not title:
                title = "Video Lecture"
            
            safe_title = title.replace("'", "\\'").replace('"', '&quot;')
            
            playlist_html += f'<button class="video-item" onclick="playVideo(\'{safe_title}\', \'{url}\')"><span class="play-icon">▶</span> {title}</button>\n'
            
        else:
            playlist_html += f'<p class="normal-text">{line}</p>\n'

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Course Player - {Config.CREDIT}</title>
    <link href="https://vjs.zencdn.net/8.10.0/video-js.css" rel="stylesheet" />
    <style>
        :root {{
            --bg-color: #0f172a;
            --container-bg: #1e293b;
            --text-color: #f8fafc;
            --text-muted: #94a3b8;
            --primary: #3b82f6;
            --border: #334155;
            --item-hover: #2dd4bf;
        }}

        [data-theme="light"] {{
            --bg-color: #f1f5f9;
            --container-bg: #ffffff;
            --text-color: #0f172a;
            --text-muted: #64748b;
            --border: #e2e8f0;
            --item-hover: #0284c7;
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', system-ui, sans-serif; transition: background-color 0.3s, color 0.3s; }}
        body {{ background-color: var(--bg-color); color: var(--text-color); height: 100vh; display: flex; flex-direction: column; overflow: hidden; }}
        
        .navbar {{ display: flex; justify-content: space-between; align-items: center; padding: 15px 25px; background: var(--container-bg); border-bottom: 1px solid var(--border); box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); z-index: 10; }}
        .navbar h1 {{ font-size: 20px; font-weight: 600; color: var(--primary); }}
        .theme-btn {{ background: var(--border); color: var(--text-color); border: none; padding: 8px 16px; border-radius: 20px; cursor: pointer; font-weight: bold; }}
        
        .main-container {{ display: flex; flex: 1; overflow: hidden; }}
        
        .player-section {{ flex: 2; padding: 20px; display: flex; flex-direction: column; background: var(--bg-color); overflow-y: auto; }}
        .video-wrapper {{ width: 100%; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.3); background: #000; }}
        #current-title {{ margin-top: 20px; font-size: 22px; font-weight: 600; color: var(--primary); }}
        #current-status {{ margin-top: 5px; color: var(--text-muted); font-size: 14px; }}
        
        .playlist-section {{ flex: 1; min-width: 350px; max-width: 450px; background: var(--container-bg); border-left: 1px solid var(--border); display: flex; flex-direction: column; }}
        .playlist-header {{ padding: 15px 20px; border-bottom: 1px solid var(--border); font-weight: 600; font-size: 18px; }}
        .playlist-content {{ flex: 1; overflow-y: auto; padding: 15px; }}
        
        .topic-heading {{ font-size: 16px; font-weight: 700; color: var(--text-muted); margin: 25px 0 10px 0; text-transform: uppercase; letter-spacing: 1px; border-bottom: 1px solid var(--border); padding-bottom: 5px; }}
        .topic-heading:first-child {{ margin-top: 0; }}
        .video-item {{ display: block; width: 100%; text-align: left; background: transparent; border: 1px solid var(--border); color: var(--text-color); padding: 12px 15px; margin-bottom: 8px; border-radius: 8px; cursor: pointer; font-size: 15px; transition: all 0.2s; word-wrap: break-word; line-height: 1.4; }}
        .video-item:hover, .video-item.active {{ background: var(--border); border-color: var(--item-hover); color: var(--item-hover); transform: translateX(5px); }}
        .play-icon {{ font-size: 12px; margin-right: 8px; opacity: 0.7; }}
        .normal-text {{ font-size: 14px; color: var(--text-muted); margin-bottom: 10px; }}

        ::-webkit-scrollbar {{ width: 8px; }}
        ::-webkit-scrollbar-track {{ background: var(--bg-color); }}
        ::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 4px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: var(--text-muted); }}

        @media (max-width: 900px) {{
            .main-container {{ flex-direction: column; overflow-y: auto; }}
            .player-section {{ flex: none; height: auto; }}
            .playlist-section {{ flex: none; max-width: 100%; border-left: none; border-top: 1px solid var(--border); overflow: visible; }}
            .playlist-content {{ overflow: visible; }}
            body {{ overflow: auto; }}
        }}
    </style>
</head>
<body>

    <div class="navbar">
        <h1>📚 Course Player</h1>
        <button class="theme-btn" onclick="toggleTheme()">🌓 Toggle Theme</button>
    </div>

    <div class="main-container">
        <div class="player-section">
            <div class="video-wrapper">
                <video id="vid-player" class="video-js vjs-fluid vjs-big-play-centered vjs-theme-city" controls preload="auto" data-setup='{{"playbackRates": [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2, 2.5, 3, 3.5, 4]}}'>
                    <p class="vjs-no-js">To view this video please enable JavaScript.</p>
                </video>
            </div>
            <div id="current-title">Select a video from the playlist to start</div>
            <div id="current-status">Waiting for selection...</div>
        </div>

        <div class="playlist-section">
            <div class="playlist-header">Course Content</div>
            <div class="playlist-content" id="playlist">
                {playlist_html}
            </div>
        </div>
    </div>

    <script src="https://vjs.zencdn.net/8.10.0/video.min.js"></script>
    <script>
        var player = videojs('vid-player');
        
        function playVideo(title, url) {{
            document.getElementById('current-title').innerText = title;
            document.getElementById('current-status').innerText = "Playing...";
            
            player.src({{ src: url }});
            player.play();
            
            document.querySelectorAll('.video-item').forEach(btn => btn.classList.remove('active'));
            event.currentTarget.classList.add('active');
            
            if (window.innerWidth <= 900) {{
                window.scrollTo({{ top: 0, behavior: 'smooth' }});
            }}
        }}

        function toggleTheme() {{
            const body = document.body;
            if (body.getAttribute('data-theme') === 'light') {{
                body.removeAttribute('data-theme');
                localStorage.setItem('theme', 'dark');
            }} else {{
                body.setAttribute('data-theme', 'light');
                localStorage.setItem('theme', 'light');
            }}
        }}

        if (localStorage.getItem('theme') === 'light') {{
            document.body.setAttribute('data-theme', 'light');
        }}
    </script>

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
    
    if Config.DUMP_CHANNEL:
        try:
            dump_msg = await message.copy(Config.DUMP_CHANNEL)
            await dump_msg.reply_text(f"👤 User: {message.from_user.mention} (`{message.from_user.id}`)")
        except Exception as e:
            print(f"Dump error: {e}")

    if Config.LOG_CHANNEL:
        try:
            await client.send_message(Config.LOG_CHANNEL, f"📝 User {message.from_user.mention} requested conversion for: `{file_name}`")
        except:
            pass

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

        if not os.path.exists("downloads"):
            os.makedirs("downloads")
            
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
        try:
            user_id = int(message.command)
            await db.ban_user(user_id)
            await message.reply(f"✅ User {user_id} has been banned.")
        except ValueError:
            await message.reply("⚠️ Please provide a valid numeric User ID.")

@bot.on_message(filters.command("unban") & filters.user(Config.ADMINS))
async def unban_cmd(client, message):
    if len(message.command) > 1:
        try:
            user_id = int(message.command)
            await db.unban_user(user_id)
            await message.reply(f"✅ User {user_id} has been unbanned.")
        except ValueError:
            await message.reply("⚠️ Please provide a valid numeric User ID.")

@bot.on_message(filters.command("users") & filters.user(Config.ADMINS))
async def users_cmd(client, message):
    users = await db.get_all_users()
    await message.reply(f"📊 Total Users: {len(users)}")

# --- DUMMY WEB SERVER ---
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
    await idle()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
