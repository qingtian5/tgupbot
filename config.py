"""Configuration for the Telegram bot.

Environment variables are loaded from a .env file or the system environment.
See .env.example for a list of all supported variables.
"""

import os

# Map province names to their environment variable names
PROVINCE_CHANNEL_ENV: dict[str, str] = {
    "北京": "CHANNEL_BEIJING",
    "天津": "CHANNEL_TIANJIN",
    "上海": "CHANNEL_SHANGHAI",
    "重庆": "CHANNEL_CHONGQING",
    "河北": "CHANNEL_HEBEI",
    "山西": "CHANNEL_SHANXI",
    "辽宁": "CHANNEL_LIAONING",
    "吉林": "CHANNEL_JILIN",
    "黑龙江": "CHANNEL_HEILONGJIANG",
    "江苏": "CHANNEL_JIANGSU",
    "浙江": "CHANNEL_ZHEJIANG",
    "安徽": "CHANNEL_ANHUI",
    "福建": "CHANNEL_FUJIAN",
    "江西": "CHANNEL_JIANGXI",
    "山东": "CHANNEL_SHANDONG",
    "河南": "CHANNEL_HENAN",
    "湖北": "CHANNEL_HUBEI",
    "湖南": "CHANNEL_HUNAN",
    "广东": "CHANNEL_GUANGDONG",
    "海南": "CHANNEL_HAINAN",
    "四川": "CHANNEL_SICHUAN",
    "贵州": "CHANNEL_GUIZHOU",
    "云南": "CHANNEL_YUNNAN",
    "陕西": "CHANNEL_SHAANXI",
    "甘肃": "CHANNEL_GANSU",
    "青海": "CHANNEL_QINGHAI",
    "内蒙古": "CHANNEL_INNER_MONGOLIA",
    "广西": "CHANNEL_GUANGXI",
    "西藏": "CHANNEL_TIBET",
    "宁夏": "CHANNEL_NINGXIA",
    "新疆": "CHANNEL_XINJIANG",
    "香港": "CHANNEL_HONGKONG",
    "澳门": "CHANNEL_MACAO",
    "台湾": "CHANNEL_TAIWAN",
}


def get_bot_token() -> str:
    """Return the Telegram bot token. Raises ValueError if not set."""
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        raise ValueError("BOT_TOKEN environment variable is required")
    return token


def get_admin_ids() -> list[int]:
    """Return the list of admin Telegram user IDs."""
    raw = os.environ.get("ADMIN_IDS", "").strip()
    if not raw:
        return []
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def get_main_channel() -> str:
    """Return the main channel ID/username (e.g. '@mychannel' or '-100123456789')."""
    return os.environ.get("MAIN_CHANNEL", "").strip()


def get_province_channels() -> dict[str, str]:
    """Return a mapping of province name -> channel ID for configured provinces."""
    channels: dict[str, str] = {}
    for province, env_var in PROVINCE_CHANNEL_ENV.items():
        value = os.environ.get(env_var, "").strip()
        if value:
            channels[province] = value
    return channels
