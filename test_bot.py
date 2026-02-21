"""Unit tests for bot.py and config.py (no live Telegram connection needed)."""

import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Stub out telegram / dotenv so tests run without those packages installed
# ---------------------------------------------------------------------------


def _make_telegram_stub():
    """Create a minimal telegram package stub."""
    telegram = types.ModuleType("telegram")
    ext = types.ModuleType("telegram.ext")
    for cls in (
        "Application",
        "CallbackQueryHandler",
        "CommandHandler",
        "ContextTypes",
        "MessageHandler",
        "filters",
    ):
        setattr(ext, cls, MagicMock())
    for cls in (
        "InlineKeyboardButton",
        "InlineKeyboardMarkup",
        "InputMediaDocument",
        "InputMediaPhoto",
        "InputMediaVideo",
        "Message",
        "Update",
    ):
        setattr(telegram, cls, MagicMock())
    telegram.ext = ext
    sys.modules.setdefault("telegram", telegram)
    sys.modules.setdefault("telegram.ext", ext)


_make_telegram_stub()
# Stub dotenv
dotenv_stub = types.ModuleType("dotenv")
dotenv_stub.load_dotenv = lambda: None
sys.modules.setdefault("dotenv", dotenv_stub)

import config  # noqa: E402  (import after stubs)
import bot  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers for building fake Message objects
# ---------------------------------------------------------------------------


def _msg(text=None, caption=None):
    m = MagicMock()
    m.text = text
    m.caption = caption
    m.media_group_id = None
    return m


# ---------------------------------------------------------------------------
# Tests: extract_province
# ---------------------------------------------------------------------------


class TestExtractProvince(unittest.TestCase):
    def test_chinese_colon(self):
        msgs = [_msg(text="姓名：张三\n现居：广东\n年龄：25")]
        self.assertEqual(bot.extract_province(msgs), "广东")

    def test_ascii_colon(self):
        msgs = [_msg(text="现居:上海")]
        self.assertEqual(bot.extract_province(msgs), "上海")

    def test_province_in_caption(self):
        msgs = [_msg(caption="现居：四川")]
        self.assertEqual(bot.extract_province(msgs), "四川")

    def test_no_match(self):
        msgs = [_msg(text="这里没有地区信息")]
        self.assertIsNone(bot.extract_province(msgs))

    def test_empty_list(self):
        self.assertIsNone(bot.extract_province([]))

    def test_partial_province_in_location(self):
        """Province name embedded in a longer location string."""
        msgs = [_msg(text="现居：广东省广州市")]
        self.assertEqual(bot.extract_province(msgs), "广东")

    def test_multiple_messages(self):
        msgs = [_msg(text="其他信息"), _msg(text="现居：黑龙江")]
        self.assertEqual(bot.extract_province(msgs), "黑龙江")

    def test_inner_mongolia(self):
        msgs = [_msg(text="现居：内蒙古呼和浩特")]
        self.assertEqual(bot.extract_province(msgs), "内蒙古")

    def test_whitespace_after_colon(self):
        msgs = [_msg(text="现居：  浙江  ")]
        self.assertEqual(bot.extract_province(msgs), "浙江")


# ---------------------------------------------------------------------------
# Tests: config helpers
# ---------------------------------------------------------------------------


class TestConfig(unittest.TestCase):
    def test_get_bot_token_raises_when_missing(self):
        with patch.dict(os.environ, {"BOT_TOKEN": ""}):
            with self.assertRaises(ValueError):
                config.get_bot_token()

    def test_get_bot_token_returns_value(self):
        with patch.dict(os.environ, {"BOT_TOKEN": "abc123"}):
            self.assertEqual(config.get_bot_token(), "abc123")

    def test_get_admin_ids_empty(self):
        with patch.dict(os.environ, {"ADMIN_IDS": ""}):
            self.assertEqual(config.get_admin_ids(), [])

    def test_get_admin_ids_single(self):
        with patch.dict(os.environ, {"ADMIN_IDS": "123"}):
            self.assertEqual(config.get_admin_ids(), [123])

    def test_get_admin_ids_multiple(self):
        with patch.dict(os.environ, {"ADMIN_IDS": "1,2,3"}):
            self.assertEqual(config.get_admin_ids(), [1, 2, 3])

    def test_get_province_channels_returns_only_configured(self):
        env = {"CHANNEL_GUANGDONG": "@gd", "CHANNEL_BEIJING": ""}
        with patch.dict(os.environ, env, clear=False):
            channels = config.get_province_channels()
            self.assertIn("广东", channels)
            self.assertNotIn("北京", channels)
            self.assertEqual(channels["广东"], "@gd")

    def test_province_channel_env_covers_all_provinces(self):
        """All province keys in PROVINCE_CHANNEL_ENV should be non-empty strings."""
        for province, env_var in config.PROVINCE_CHANNEL_ENV.items():
            self.assertIsInstance(province, str)
            self.assertTrue(province, f"Empty province key found")
            self.assertTrue(env_var.startswith("CHANNEL_"), f"Bad env var: {env_var}")


# ---------------------------------------------------------------------------
# Tests: _is_admin helper
# ---------------------------------------------------------------------------


class TestIsAdmin(unittest.TestCase):
    def test_admin_id_recognised(self):
        with patch.dict(os.environ, {"ADMIN_IDS": "42"}):
            self.assertTrue(bot._is_admin(42))

    def test_non_admin_rejected(self):
        with patch.dict(os.environ, {"ADMIN_IDS": "42"}):
            self.assertFalse(bot._is_admin(99))


if __name__ == "__main__":
    unittest.main()
