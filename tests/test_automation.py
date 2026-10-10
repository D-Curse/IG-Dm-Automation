import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.pop('INSTAGRAM_ACCOUNT_ID', None)
os.environ.pop('INSTAGRAM_ACCESS_TOKEN', None)
import app as module


class AutomationTests(unittest.TestCase):
    def setUp(self):
        self.mode_patch = patch.object(module, 'live', return_value=False)
        self.mode_patch.start()
        self.addCleanup(self.mode_patch.stop)
        module.analytics_cache.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = module.DB
        module.DB = Path(self.tmp.name) / 'test.db'
        module.init_db()
        module.sync_reels()
        self.client = module.app.test_client()
        self.client.get('/')
        with self.client.session_transaction() as session:
            self.headers = {'X-CSRF-Token': session['csrf']}

    def tearDown(self):
        module.DB = self.old_db
        self.tmp.cleanup()

    def test_replied_comment_skips_dm_and_runs_are_idempotent(self):
        response = self.client.post('/api/reels/demo-0', json=dict(keywords='link, info', reply='Check your inbox', dm='Here is your link', enabled=True), headers=self.headers)
        self.assertEqual(response.status_code, 200)
        for _ in range(2):
            self.assertEqual(self.client.post('/api/run', json={}, headers=self.headers).status_code, 200)
        actions = self.client.get('/api/state').json['actions']
        self.assertEqual(len(actions), 3)
        self.assertEqual(sum(a['status'] == 'completed' for a in actions), 2)
        self.assertEqual(next(a for a in actions if a['username'] == 'alex.studio')['status'], 'skipped')

    def test_mutations_need_csrf_and_rules_are_validated(self):
        self.assertEqual(self.client.post('/api/run').status_code, 403)
        self.assertEqual(self.client.post('/api/reels/demo-0', json={}, headers=self.headers).status_code, 400)

    def test_keyword_boundaries(self):
        self.assertTrue(module.matches('INFO please!', 'link, info'))
        self.assertFalse(module.matches('informative', 'info'))

    def test_demo_analytics_and_unknown_reel(self):
        data = self.client.get('/api/reels/demo-0/analytics').json
        self.assertEqual(data['mode'], 'demo')
        self.assertEqual(data['metrics']['views'], 12480)
        self.assertEqual(self.client.get('/api/reels/unknown/analytics').status_code, 404)

    def test_partial_analytics_preserves_zero_and_missing_values(self):
        with module.connect() as db:
            db.execute("INSERT INTO reels(id) VALUES ('real-123')")
        def response(path, **kwargs):
            if path == 'real-123':
                return {'like_count': 0, 'comments_count': 2}
            if kwargs['metric'] == 'views':
                return {'data': [{'values': [{'value': 0}]}]}
            raise RuntimeError('Permission denied')
        with patch.object(module, 'live', return_value=True), patch.object(module.api, 'call', side_effect=response) as calls, patch.object(module.api, 'pages', return_value=[]):
            data = self.client.get('/api/reels/real-123/analytics').json
            self.assertEqual(data['metrics']['views'], 0)
            self.assertIsNone(data['metrics']['reach'])
            self.assertEqual(data['metrics']['comments'], 2)
            self.assertTrue(any('Development mode' in note for note in data['notes']))
            before = calls.call_count
            self.client.get('/api/reels/real-123/analytics')
            self.assertEqual(calls.call_count, before)

    def test_live_existing_owner_reply_prevents_all_sends(self):
        with module.connect() as db:
            reel = dict(db.execute('SELECT * FROM reels LIMIT 1').fetchone())
        comment = {'id': 'real-comment', 'text': 'info', 'username': 'viewer'}
        with patch.object(module, 'live', return_value=True), patch.dict(os.environ, {'INSTAGRAM_ACCOUNT_ID': 'owner'}), patch.object(module.api, 'pages', return_value=iter([{'text': reel['reply'], 'from': {'id': 'owner'}}])), patch.object(module.api, 'call') as send:
            module.process_comment(reel, comment)
            send.assert_not_called()
        with module.connect() as db:
            self.assertEqual(db.execute("SELECT status FROM actions WHERE comment_id='real-comment'").fetchone()[0], 'skipped')

    def test_failed_send_is_not_retried(self):
        with module.connect() as db:
            reel = dict(db.execute('SELECT * FROM reels LIMIT 1').fetchone())
        comment = dict(id='failed-comment', text='info', timestamp=module.datetime.now(module.timezone.utc).isoformat())
        with patch.object(module, 'live', return_value=True), patch.dict(os.environ, {'INSTAGRAM_ACCOUNT_ID': 'owner'}), patch.object(module.api, 'pages', return_value=[]), patch.object(module.api, 'call', side_effect=RuntimeError('Timed out')) as send:
            module.process_comment(reel, comment)
            module.process_comment(reel, comment)
            self.assertEqual(send.call_count, 1)


if __name__ == '__main__':
    unittest.main()
