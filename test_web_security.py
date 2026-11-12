"""Smoke tests for the private web authentication gate."""
import base64
import os
import subprocess
import sys
import unittest

class WebSecurityTests(unittest.TestCase):
    def test_missing_credentials_prevents_start(self):
        env = dict(os.environ)
        env.pop("NOVA_AUTH_USER", None)
        env.pop("NOVA_AUTH_PASSWORD", None)
        result = subprocess.run([sys.executable, "web_studio.py"], env=env,
                                capture_output=True, text=True, timeout=20)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("NOVA_AUTH_USER", result.stderr + result.stdout)

    def test_remote_bind_requires_https_proxy_flag(self):
        env = dict(os.environ, NOVA_AUTH_USER="owner",
                   NOVA_AUTH_PASSWORD="long-private-test-password",
                   NOVA_HOST="0.0.0.0")
        env.pop("NOVA_BEHIND_HTTPS_PROXY", None)
        result = subprocess.run([sys.executable, "web_studio.py"], env=env,
                                capture_output=True, text=True, timeout=20)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("HTTPS", result.stderr + result.stdout)

if __name__ == "__main__":
    unittest.main()
