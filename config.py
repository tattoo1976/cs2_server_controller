# config.py
# Public-safe defaults. Override locally via config.yaml.

# Log directory used by the controller.
LOG_DIR = r"D:\\path\\to\\cs2\\game\\csgo\\logs"

# RCON defaults (set your local real values).
RCON_HOST = "127.0.0.1"
RCON_PORT = 27015
RCON_PASSWORD = "CHANGE_ME"

# Admin steam id placeholder.
ADMIN_STEAMID = "[U:1:YOUR_ACCOUNT_ID]"

# Match settings.
MAX_ROUNDS = 24
TAUNT_CHANCE = 0.25

# Public map pool default.
AVAILABLE_MAPS = ["dust2", "inferno", "ancient", "mirage"]

# Legacy options (kept for compatibility).
LOG_MONITOR_LATEST = 3
CLEAN_OLD_LOGS = False
MAX_LOG_FILES_KEEP = 10
