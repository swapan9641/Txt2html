import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    API_ID = int(os.environ.get("API_ID", "0"))
    API_HASH = os.environ.get("API_HASH", "")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
    
    # Database
    MONGO_URI = os.environ.get("MONGO_URI", "")
    
    # Channels & Admins
    ADMINS = [int(x) for x in os.environ.get("ADMINS", "").split(",") if x]
    LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "0"))
    DUMP_CHANNEL = int(os.environ.get("DUMP_CHANNEL", "0"))
    FORCE_SUB_CHANNEL = os.environ.get("FORCE_SUB_CHANNEL", "0") # Channel ID or Username
    
    # Customization
    CREDIT = os.environ.get("CREDIT", "Created by Suman")
    PORT = int(os.environ.get("PORT", "8080"))
