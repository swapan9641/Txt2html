import os
import sys
import asyncio
import re
import base64
import urllib.parse
import html
import json  # <--- MAKE SURE THIS IS ADDED!
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
    output = []
    seen_urls = set()
    
    # --- 1. MULTI-PASS BASE64 UNPACKER ---
    for b64_match in re.finditer(r'atob\(\s*[\'"]([A-Za-z0-9+/=\s]+)[\'"]\s*\)', html_content):
        try:
            cleaned = re.sub(r'\s+', '', b64_match.group(1))
            decoded = base64.b64decode(cleaned).decode('utf-8', errors='ignore')
            html_content += "\n" + decoded 
        except: pass

    # --- 2. ADVANCED XOR DECRYPTION ---
    xor_match = re.search(r"const encodedContent\s*=\s*'([^']+)';", html_content)
    if xor_match:
        try:
            encoded = xor_match.group(1)
            key = b"TusharSuperSecreT2025!" 
            cleaned = re.sub(r'[^A-Za-z0-9+/=]', '', encoded)
            xor_bytes = base64.b64decode(cleaned)
            base64_bytes = bytearray(xor_bytes[i] ^ key[i % len(key)] for i in range(len(xor_bytes)))
            cleaned_b64 = re.sub(r'[^A-Za-z0-9+/=]', '', base64_bytes.decode('utf-8'))
            decoded_html = base64.b64decode(cleaned_b64).decode('utf-8', errors='ignore')
            html_content += "\n" + decoded_html
        except: pass

    # --- 3. JSON CONFIG EXTRACTOR ---
    json_match = re.search(r'data:\s*(\{".*?\})\s*\};', html_content, re.DOTALL)
    if json_match:
        try:
            json_data = json.loads(json_match.group(1))
            for heading, items in json_data.items():
                output.append(f"\n## {heading}\n")
                if not isinstance(items, list): continue # Failsafe
                
                for item in items:
                    if not isinstance(item, dict): continue # Failsafe
                    
                    title = str(item.get('title', 'Video Lecture'))
                    link_raw = item.get('link', '')
                    file_type = str(item.get('type', 'VIDEO'))
                    
                    if isinstance(link_raw, list): link_raw = link_raw # Failsafe
                    
                    try:
                        link = base64.b64decode(str(link_raw)).decode('utf-8')
                    except:
                        link = str(link_raw)
                        
                    clean_url = link.split('?') if 'http://googleusercontent.com' not in link else link
                    
                    # Force strings to prevent unhashable type list error
                    if link and str(link) not in seen_urls and str(clean_url) not in seen_urls:
                        seen_urls.add(str(link))
                        seen_urls.add(str(clean_url))
                        icon = "📄" if file_type.upper() == "PDF" else "▶️"
                        output.append(f"{icon} {title}:{link}")
        except: pass

    # --- 4. THE GOD-TIER HTML DOM PARSER ---
    soup = BeautifulSoup(html_content, 'lxml')
    generic_words = {'play', 'watch', 'download', 'view', 'pdf', 'original', 'copy', 'close', 'link', 'click here', 'video', 'notes'}

    def unwrap_url(raw_url):
        try:
            parsed = urllib.parse.urlparse(str(raw_url))
            queries = urllib.parse.parse_qs(parsed.query)
            for key, value_list in queries.items():
                for val in value_list:
                    if str(val).startswith('http'):
                        return urllib.parse.unquote(str(val))
        except: pass
        return str(raw_url)

    for el in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'a', 'button', 'div', 'li', 'p']):
        try:
            # 1. PARSE HEADINGS SAFELY
            if el.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                text = el.get_text(strip=True)
                if text:
                    # Failsafe integer extraction (fixes the 'h2' error!)
                    level_match = re.search(r'\d+', el.name)
                    level = int(level_match.group()) if level_match else 2
                    output.append(f"\n{'#' * level} {html.unescape(text)}\n")
                continue
                
            # 2. PARSE NORMAL PARAGRAPHS
            if el.name == 'p':
                text = el.get_text(strip=True)
                raw_target = f"{el.get('onclick', '')} {el.get('href', '')}"
                if text and "http" not in raw_target:
                    output.append(f"{html.unescape(text)}")
                continue

            # 3. PARSE LINKS/BUTTONS
            raw_target = f"{el.get('onclick', '')} {el.get('href', '')} {el.get('data-url', '')} {el.get('data-src', '')}"
            url_match = re.search(r"(https?://[^\s'\"<>]+)", raw_target)
            
            if url_match:
                url = unwrap_url(url_match.group(1))
                
                # Force URL to string to prevent "unhashable type: 'list'" error
                url = str(url)
                clean_url = url.split('?') if 'http://googleusercontent.com' not in url else url
                clean_url = str(clean_url)
                
                if url in seen_urls or clean_url in seen_urls:
                    continue

                text = el.get_text(separator=' ', strip=True)
                
                if not text or text.lower() in generic_words:
                    js_title = re.search(r"openVideoPopup\([^,]+,\s*['\"][^'\"]+['\"],\s*['\"]([^'\"]+)['\"]", raw_target)
                    if js_title:
                        text = js_title.group(1)
                    else:
                        parent = el.parent
                        if parent:
                            parent_text = parent.get_text(separator=' ', strip=True)
                            for gw in generic_words:
                                parent_text = re.sub(rf'\b{gw}\b', '', parent_text, flags=re.IGNORECASE)
                            text = re.sub(r'^\d+[\.\)\-]?\s*', '', parent_text).strip()
                            
                            if not text:
                                # Some attributes might be lists in BS4, force string!
                                title_attr = el.get('title', '')
                                aria_attr = el.get('aria-label', '')
                                text = str(title_attr if isinstance(title_attr, list) else title_attr)
                                if not text:
                                    text = str(aria_attr if isinstance(aria_attr, list) else aria_attr)

                text = html.unescape(text).strip(':').strip()
                
                if not text or text.lower() in generic_words:
                    text = "Lecture/Document" 

                if '.pdf' in url.lower() or 'pdf' in text.lower():
                    icon = "📄"
                elif '.jpg' in url.lower() or '.png' in url.lower() or 'png' in text.lower():
                    icon = "🖼️"
                else:
                    icon = "▶️"

                output.append(f"{icon} {text}:{url}")
                seen_urls.add(url)
                seen_urls.add(clean_url)
                
        except Exception as e:
            # Safely ignore completely broken elements instead of crashing the whole bot
            continue

    try:
        credit_text = Config.CREDIT
    except:
        credit_text = "S_MAHATO"
        
    output.append(f"\n\n--- {credit_text} ---")
    final_text = "\n".join(output)
    
    return re.sub(r'\n{3,}', '\n\n', final_text).strip()

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
            
            # If it's a PDF, direct them straight to Chrome instead of the video player
            if '📄' in title or '.pdf' in url.lower():
                playlist_html += f'<button class="video-item" onclick="openExternal(\'{url}\')"><span class="play-icon">📄</span> {title}</button>\n'
            else:
                playlist_html += f'<button class="video-item" onclick="playVideo(\'{safe_title}\', \'{url}\')"><span class="play-icon">▶️</span> {title}</button>\n'
            
        else:
            playlist_html += f'<p class="normal-text">{line}</p>\n'

    # --- 1. GENERATE THE RAW ADVANCED PLAYER HTML ---
    raw_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Premium Course Player - S_MAHATO</title>
    <link href="https://vjs.zencdn.net/8.10.0/video-js.css" rel="stylesheet" />
    <style>
        /* SMOOTH AI DARK MODE VARIABLES */
        :root {{ 
            --bg: #0b0f19; 
            --panel: #161f33; 
            --text: #f8fafc; 
            --muted: #94a3b8; 
            --accent: #3b82f6; 
            --accent-glow: rgba(59, 130, 246, 0.4);
            --border: #2dd4bf; 
            --item-hover: rgba(45, 212, 191, 0.15);
        }}
        [data-theme="light"] {{ 
            --bg: #f1f5f9; 
            --panel: #ffffff; 
            --text: #0f172a; 
            --muted: #64748b; 
            --accent: #2563eb; 
            --accent-glow: rgba(37, 99, 235, 0.3);
            --border: #e2e8f0; 
            --item-hover: rgba(37, 99, 235, 0.08);
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', system-ui, sans-serif; }}
        body {{ background-color: var(--bg); color: var(--text); height: 100vh; display: flex; flex-direction: column; overflow: hidden; transition: background-color 0.5s ease, color 0.5s ease; }}
        
        .navbar {{ display: flex; justify-content: space-between; align-items: center; padding: 18px 30px; background: var(--panel); box-shadow: 0 4px 20px rgba(0,0,0,0.1); z-index: 10; transition: background 0.5s ease; }}
        .navbar h1 {{ font-size: 22px; font-weight: 700; color: var(--accent); display: flex; align-items: center; gap: 10px; text-shadow: 0 0 15px var(--accent-glow); transition: color 0.5s ease; }}
        
        .theme-btn {{ background: transparent; border: 2px solid var(--accent); color: var(--text); padding: 8px 18px; border-radius: 20px; cursor: pointer; font-weight: bold; transition: all 0.3s ease; }}
        .theme-btn:hover {{ background: var(--accent); color: white; box-shadow: 0 0 15px var(--accent-glow); }}
        
        .main-container {{ display: flex; flex: 1; overflow: hidden; }}
        
        .player-section {{ flex: 2; padding: 25px; display: flex; flex-direction: column; overflow-y: auto; }}
        .video-wrapper {{ width: 100%; border-radius: 16px; overflow: hidden; box-shadow: 0 15px 35px rgba(0,0,0,0.3); background: #000; border: 1px solid rgba(255,255,255,0.05); }}
        
        #vid-title {{ margin-top: 25px; font-size: 24px; font-weight: 700; color: var(--text); transition: color 0.5s ease; }}
        #vid-status {{ margin-top: 8px; color: var(--muted); font-size: 15px; font-weight: 500; transition: color 0.5s ease; }}
        
        /* CHROME EXTERNAL BUTTON */
        .chrome-btn {{ margin-top: 20px; padding: 15px 25px; background: linear-gradient(135deg, #3b82f6, #2563eb); color: white; border: none; border-radius: 12px; cursor: pointer; font-size: 16px; font-weight: bold; display: none; align-items: center; justify-content: center; gap: 10px; width: 100%; transition: all 0.3s ease; box-shadow: 0 8px 20px rgba(37, 99, 235, 0.3); }}
        .chrome-btn:hover {{ transform: translateY(-3px); box-shadow: 0 12px 25px rgba(37, 99, 235, 0.5); }}
        .error-pulse {{ animation: red-pulse 1.5s infinite; background: linear-gradient(135deg, #ef4444, #dc2626) !important; box-shadow: 0 8px 20px rgba(239, 68, 68, 0.4) !important; }}
        
        @keyframes red-pulse {{
            0% {{ transform: scale(1); }}
            50% {{ transform: scale(1.02); }}
            100% {{ transform: scale(1); }}
        }}

        .playlist-section {{ flex: 1; min-width: 380px; max-width: 450px; background: var(--panel); display: flex; flex-direction: column; border-left: 1px solid rgba(255,255,255,0.05); transition: background 0.5s ease; box-shadow: -5px 0 20px rgba(0,0,0,0.05); }}
        .playlist-header {{ padding: 20px; border-bottom: 1px solid rgba(128,128,128,0.1); font-weight: 700; font-size: 18px; color: var(--accent); }}
        .playlist-content {{ flex: 1; overflow-y: auto; padding: 15px 20px; scroll-behavior: smooth; }}
        
        .topic-heading {{ font-size: 14px; font-weight: 800; color: var(--muted); margin: 30px 0 12px 0; text-transform: uppercase; letter-spacing: 1.5px; }}
        .topic-heading:first-child {{ margin-top: 0; }}
        
        .video-item {{ display: flex; align-items: flex-start; width: 100%; text-align: left; background: transparent; border: 1px solid rgba(128,128,128,0.1); color: var(--text); padding: 14px 18px; margin-bottom: 10px; border-radius: 12px; cursor: pointer; font-size: 15px; font-weight: 500; transition: all 0.3s ease; line-height: 1.5; }}
        .video-item:hover, .video-item.active {{ background: var(--item-hover); border-color: var(--border); transform: translateX(6px); color: var(--border); box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
        
        .play-icon {{ margin-right: 12px; font-size: 16px; opacity: 0.9; }}
        .normal-text {{ font-size: 14px; color: var(--muted); margin-bottom: 10px; padding: 0 5px; }}

        /* Scrollbars */
        ::-webkit-scrollbar {{ width: 6px; }}
        ::-webkit-scrollbar-track {{ background: transparent; }}
        ::-webkit-scrollbar-thumb {{ background: rgba(128,128,128,0.3); border-radius: 10px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: rgba(128,128,128,0.5); }}

        @media (max-width: 900px) {{ 
            .main-container {{ flex-direction: column; overflow-y: auto; }} 
            .player-section {{ flex: none; height: auto; padding: 15px; }} 
            .playlist-section {{ flex: none; max-width: 100%; border-left: none; box-shadow: none; overflow: visible; }} 
            .playlist-content {{ overflow: visible; }} 
            body {{ overflow: auto; }} 
        }}
    </style>
</head>
<body>
    <div class="navbar">
        <h1>✨ Course Player</h1>
        <button class="theme-btn" onclick="toggleTheme()">🌓 Theme</button>
    </div>
    
    <div class="main-container">
        <div class="player-section">
            <div class="video-wrapper">
                <video id="vid-player" class="video-js vjs-fluid vjs-big-play-centered vjs-theme-city" controls preload="auto" data-setup='{{"playbackRates": [0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2, 2.5, 3, 3.5, 4]}}'>
                    <p class="vjs-no-js">Please enable JavaScript.</p>
                </video>
            </div>
            <div id="vid-title">Select a video from the playlist to start</div>
            <div id="vid-status">Waiting for selection...</div>
            
            <button id="chrome-btn" class="chrome-btn" onclick="openExternal()">
                🌐 Open in Chrome / External Player
            </button>
        </div>
        
        <div class="playlist-section">
            <div class="playlist-header">📚 Playlist Index</div>
            <div class="playlist-content" id="playlist">
                {playlist_html}
            </div>
        </div>
    </div>
    
    <div style="text-align: center; padding: 18px; color: var(--muted); font-size: 14px; font-weight: 700; background: var(--panel); transition: background 0.5s ease;">
        🔒 Encrypted & Created by <span style="color: var(--border);">S_MAHATO</span>
    </div>

    <script src="https://vjs.zencdn.net/8.10.0/video.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/videojs-contrib-quality-levels/2.2.1/videojs-contrib-quality-levels.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/videojs-hls-quality-selector@1.1.4/dist/videojs-hls-quality-selector.min.js"></script>

    <script>
        var player = videojs('vid-player');
        
        // Initialize Quality Selector Plugin
        try {{ player.hlsQualitySelector({{ displayCurrentQuality: true }}); }} catch(e) {{}}
        
        var currentUrl = "";

        function playVideo(title, url) {{
            currentUrl = url;
            document.getElementById('vid-title').innerText = title;
            document.getElementById('vid-status').innerHTML = "⏳ Loading high-quality stream...";
            
            // Reset Chrome Button Styling
            const chromeBtn = document.getElementById('chrome-btn');
            chromeBtn.style.display = 'flex';
            chromeBtn.classList.remove('error-pulse');
            chromeBtn.innerHTML = "🌐 Open in Chrome / External Player";
            
            player.src({{ src: url }});
            player.play();
            
            document.querySelectorAll('.video-item').forEach(btn => btn.classList.remove('active'));
            event.currentTarget.classList.add('active');
            
            if (window.innerWidth <= 900) {{ window.scrollTo({{ top: 0, behavior: 'smooth' }}); }}
        }}

        function openExternal(url = null) {{
            let targetUrl = url || currentUrl;
            if (targetUrl) {{ window.open(targetUrl, '_blank'); }}
        }}

        // SMART ERROR DETECTOR
        player.on('error', function() {{
            document.getElementById('vid-status').innerHTML = "<span style='color:#ef4444; font-weight:bold;'>❌ Browser blocked playback. Please click the red button below.</span>";
            const chromeBtn = document.getElementById('chrome-btn');
            chromeBtn.classList.add('error-pulse');
            chromeBtn.innerHTML = "🚨 Play in Chrome to bypass restrictions!";
        }});

        player.on('playing', function() {{
            document.getElementById('vid-status').innerText = "▶️ Playing Smoothly";
        }});

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
        if (localStorage.getItem('theme') === 'light') {{ document.body.setAttribute('data-theme', 'light'); }}
    </script>
</body>
</html>"""

    # --- 2. ADVANCED PYTHON ENCRYPTION ENGINE (S_MAHATO Key) ---
    key = "S_MAHATO"
    b64_content = base64.b64encode(raw_html.encode('utf-8')).decode('utf-8')
    
    xor_bytes = bytearray()
    for i in range(len(b64_content)):
        char_code = ord(b64_content[i]) ^ ord(key[i % len(key)])
        xor_bytes.append(char_code)
        
    encoded_content = base64.b64encode(xor_bytes).decode('utf-8')

    # --- 3. THE SECURE S_MAHATO JAVASCRIPT WRAPPER ---
    encrypted_html_template = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Course Player - S_MAHATO</title>
</head>
<body style="margin:0; padding:0; background:#0b0f19; color:white; display:flex; justify-content:center; align-items:center; height:100vh; font-family:'Segoe UI', sans-serif;">
    <div id="loading" style="text-align:center;">
        <h2 style="color:#2dd4bf; text-shadow: 0 0 15px rgba(45, 212, 191, 0.4);">⏳ Decrypting Player...</h2>
        <p style="color:#94a3b8; font-size:15px; font-weight:bold; margin-top:10px;">Created securely by <span style="color:#f8fafc;">S_MAHATO</span></p>
    </div>
    <script>
        const encodedContent = '{encoded_content}';
        const SECRET_KEY = 'S_MAHATO';

        function xor_decrypt(data, key) {{
            let result = '';
            for (let i = 0; i < data.length; i++) {{
                let charCode = data.charCodeAt(i) ^ key.charCodeAt(i % key.length);
                result += String.fromCharCode(charCode);
            }}
            return result;
        }}
        
        setTimeout(() => {{
            try {{
                const cleanedEncodedContent = encodedContent.replace(/[^A-Za-z0-9+/=]/g, '');
                const xorContent = atob(cleanedEncodedContent); 
                const base64Content = xor_decrypt(xorContent, SECRET_KEY);
                const cleanedBase64Content = base64Content.replace(/[^A-Za-z0-9+/=]/g, '');
                const binary = atob(cleanedBase64Content); 
                
                const bytes = new Uint8Array(binary.length);
                for (let i = 0; i < binary.length; i++) {{
                    bytes[i] = binary.charCodeAt(i);
                }}

                const decodedContent = new TextDecoder('utf-8').decode(bytes);
                document.open();
                document.write(decodedContent);
                document.close();
            }} catch (e) {{
                document.getElementById('loading').innerHTML = '<h2 style="color:#ef4444;">❌ Decryption Failed.</h2><p style="color:#94a3b8;">File corrupted. Protected by S_MAHATO.</p>';
            }}
        }}, 400); // Added slight delay to show the cool loading screen
    </script>
</body>
</html>"""

    return encrypted_html_template

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
    btn = [[InlineKeyboardButton("❓ Help & Instructions", callback_data="show_help")]]
    await message.reply(
        f"Hello {message.from_user.first_name}!\n\nSend me an `.html` file to convert it to `.txt` with headings.\nSend me a `.txt` file to convert it to a Pro-Level Themed `.html` file.",
        reply_markup=InlineKeyboardMarkup(btn)
    )

@bot.on_callback_query(filters.regex("show_help"))
async def help_button_click(client, callback_query):
    help_text = "**🛠 How to Use This Bot**\n\n1. Send `.html` to get clean `.txt`\n2. Send `.txt` to get Encrypted Pro-Level `.html`\n\nEnjoy the High-Speed Conversion!"
    await callback_query.message.edit_text(help_text)

@bot.on_message(filters.command("help") & filters.private)
async def help_cmd(client: Client, message: Message):
    help_text = f"""
**🛠 How to Use This Bot**

**1. Convert HTML to TXT**
Send me any supported `.html` file. I will automatically extract all the hidden video links and give you a clean `.txt` file with proper headings.

**2. Convert TXT to Pro HTML**
Send me a `.txt` file formatted with links. I will convert it into a beautiful Advanced Course Player that is **Encrypted & Protected by mahto_420**.

**👮‍♂️ Admin Commands:**
`/users` - Check total bot users
`/ban <user_id>` - Ban a user
`/unban <user_id>` - Unban a user
`/restart` - Restart the bot server
"""
    await message.reply(help_text, disable_web_page_preview=True)

@bot.on_message(filters.document & filters.private)
async def handle_document(client: Client, message: Message):
    doc = message.document
    file_name = doc.file_name.lower()
    
    if Config.DUMP_CHANNEL:
        try:
            dump_msg = await message.copy(Config.DUMP_CHANNEL)
            await dump_msg.reply_text(f"👤 User: {message.from_user.mention} (`{message.from_user.id}`)")
        except Exception as e:
            await message.reply(f"⚠️ **DUMP CHANNEL ERROR:**\n`{e}`\n\nCheck your channel ID and Admin permissions.")

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
