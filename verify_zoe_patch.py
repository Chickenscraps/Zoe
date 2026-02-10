import unittest
import os
import sys
import yaml
import time
from unittest.mock import MagicMock, AsyncMock

# Add project root to path
sys.path.insert(0, os.getcwd())

import safety
import admin_tools

class TestZoePatch(unittest.TestCase):
    
    def test_config_loading(self):
        """Test config.yaml exists and has required keys."""
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
        self.assertIn("discord", config)
        self.assertIn("admin", config)
        self.assertIn("persona", config)
        self.assertIn("allowed_chat_channel_ids", config["discord"])
        self.assertIn("admin_user_ids", config["admin"])
        print("✅ Config loaded successfully")

    def test_safety_sanitization(self):
        """Test output sanitization."""
        # Forbidden phrases
        forbidden = [
            "system online", "module loaded", "permission check", 
            "grant permission", "deploying to netlify", "stack trace: error"
        ]
        
        for phrase in forbidden:
            clean = safety.sanitize_output(f"Hello {phrase} world", is_admin_context=False)
            self.assertNotIn(phrase, clean)
            self.assertNotIn(phrase.upper(), clean.upper())
            
        # Admin channel should ALSO be sanitized by default (unless verbose flag used, which isn't in this test)
        admin_clean = safety.sanitize_output("module loaded", is_admin_context=True)
        self.assertEqual(admin_clean, "") 
        
        print("✅ Safety sanitization passed")

    def test_mention_enforcement(self):
        """Test mention allowlist enforcement."""
        allowlist = ["Josh", "Steve"]
        
        # Test 1: Forbidden Role replacements
        text = "Contact the admin for help."
        cleaned = safety.enforce_allowlist_mentions(text, allowlist)
        self.assertNotIn("admin", cleaned.lower())
        self.assertIn("ops", cleaned.lower())
        
        print("✅ Mention enforcement passed")

    def test_admin_tools_confirmation(self):
        """Test the confirm flow."""
        user_id = 999
        args = ["rm -rf /"]
        
        # 1. Request Confirmation
        msg = admin_tools.request_confirmation("run_shell", args, user_id)
        self.assertIn("Confirm with: `!zoe confirm", msg)
        
        # Extract nonce (simple parsing)
        import re
        match = re.search(r"!zoe confirm ([a-f0-9]+)", msg)
        self.assertTrue(match)
        nonce = match.group(1)
        
        # 2. Try with wrong user
        bot_mock = MagicMock()
        res = admin_tools.process_confirmation(bot_mock, nonce, 888) # Wrong user
        self.assertIn("not for you", res)
        
        # 3. Try with correct user
        # We need to mock run_shell because it will try to execute
        original_run_shell = admin_tools.run_shell
        admin_tools.run_shell = MagicMock(return_value="Shell Executed")
        
        res = admin_tools.process_confirmation(bot_mock, nonce, user_id)
        self.assertEqual(res, "Shell Executed")
        
        # Restore
        admin_tools.run_shell = original_run_shell
        print("✅ Admin confirmation flow passed")

if __name__ == '__main__':
    unittest.main()
