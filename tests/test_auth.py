import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from werkzeug.security import generate_password_hash
import app as module

class LoginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = 'test-only-long-passphrase!'
        cls.credentials = {'username': 'admin', 'password_hash': generate_password_hash(cls.password)}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = module.DB
        module.DB = Path(self.tmp.name) / 'db.sqlite'
        module.init_db()
        self.patch = patch.object(module, 'read_credentials', return_value=self.credentials)
        self.patch.start()
        self.client = module.app.test_client()

    def tearDown(self):
        self.patch.stop()
        module.DB = self.old_db
        self.tmp.cleanup()

    def signin(self, password=None):
        self.client.get('/login')
        with self.client.session_transaction() as s:
            csrf = s['csrf']
        return self.client.post('/login', data={'username':'admin', 'password':password or self.password, 'csrf':csrf})

    def test_dashboard_and_apis_require_login_but_policies_are_public(self):
        self.assertEqual(self.client.get('/').status_code, 302)
        self.assertEqual(self.client.get('/api/state').status_code, 401)
        self.assertEqual(self.client.post('/api/run').status_code, 401)
        with self.client.get('/static/legal/privacy-policy.html') as response:
            self.assertEqual(response.status_code, 200)

    def test_login_logout_csrf_and_revocation(self):
        self.assertEqual(self.client.post('/login', data={'username':'admin','password':self.password}).status_code, 403)
        self.assertEqual(self.signin().status_code, 302)
        self.assertEqual(self.client.get('/api/state').status_code, 200)
        with self.client.session_transaction() as s:
            token, sid = s['csrf'], s['sid']
        self.assertEqual(self.client.post('/logout').status_code, 403)
        self.assertEqual(self.client.post('/logout',data={'csrf':token}).status_code, 302)
        self.assertEqual(self.client.get('/api/state').status_code, 401)
        with module.connect() as db:
            self.assertIsNone(db.execute('SELECT * FROM dashboard_sessions WHERE token=?',(sid,)).fetchone())

    def test_failed_attempts_rate_limited(self):
        for _ in range(5):
            self.assertEqual(self.signin('incorrect').status_code, 401)
        self.assertEqual(self.signin().status_code, 429)

    def test_idle_expiry_and_password_change_revoke_access(self):
        self.signin()
        with self.client.session_transaction() as s:
            s['last_seen'] = time.time() - 1801
        self.assertEqual(self.client.post('/api/run').status_code, 401)
        self.assertEqual(self.client.get('/api/state').status_code, 401)
        self.signin()
        with patch.object(module, 'read_credentials', return_value={**self.credentials,'username':'new-admin'}):
            self.assertEqual(self.client.get('/api/state').status_code, 401)

    def test_missing_credentials_fail_closed_and_security_headers(self):
        with patch.object(module, 'read_credentials', return_value=None):
            response = self.client.get('/login')
            self.assertEqual(response.status_code, 503)
            self.assertIn(b'setup_login.py',response.data)
        self.assertEqual(response.headers['X-Frame-Options'],'DENY')
        self.assertEqual(response.headers['Cache-Control'],'no-store')
        self.assertIn('HttpOnly', response.headers.get('Set-Cookie',''))

if __name__ == '__main__':
    unittest.main()
