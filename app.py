import os
import re
import secrets
import sqlite3
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import time

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session

load_dotenv()
ROOT = Path(__file__).parent
(ROOT / 'instance').mkdir(exist_ok=True)
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY') or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict', MAX_CONTENT_LENGTH=65536)
DB = ROOT / 'instance' / 'automation.db'
run_lock = threading.Lock()
analytics_cache = {}
analytics_lock = threading.Lock()


@contextmanager
def connect():
    db = sqlite3.connect(DB, timeout=30)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()


def init_db():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS reels (id TEXT PRIMARY KEY, caption TEXT, url TEXT,
          timestamp TEXT, keywords TEXT DEFAULT 'link, info', reply TEXT DEFAULT 'Check your inbox ✨',
          dm TEXT DEFAULT 'Hey! Thanks for your interest. Here is the link: https://example.com', enabled INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS actions (comment_id TEXT PRIMARY KEY, reel_id TEXT, username TEXT,
          comment TEXT, status TEXT, detail TEXT, updated TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, message TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
        INSERT OR IGNORE INTO settings VALUES ('background', '0');
        INSERT OR IGNORE INTO settings VALUES ('last_sync', 'Never');
        ''')


def live():
    return bool(os.getenv('INSTAGRAM_ACCOUNT_ID') and os.getenv('INSTAGRAM_ACCESS_TOKEN'))


def setting(key):
    with connect() as db:
        return db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()[0]


def event(message):
    with connect() as db:
        db.execute('INSERT INTO events(message) VALUES (?)', (message,))
        db.execute('DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT 100)')


class Instagram:
    def call(self, path, method='GET', **params):
        url = f"https://graph.instagram.com/{os.getenv('INSTAGRAM_API_VERSION', 'v25.0')}/{path}"
        try:
            response = requests.request(method, url, params=params if method == 'GET' else None,
                                        json=params if method != 'GET' else None,
                                        headers={'Authorization': 'Bearer ' + os.environ['INSTAGRAM_ACCESS_TOKEN']}, timeout=25)
            data = response.json()
        except (requests.RequestException, ValueError):
            raise RuntimeError('Instagram could not be reached. Check connection and activity before retrying.') from None
        if not response.ok or 'error' in data:
            error = data.get('error', {})
            raise RuntimeError(f"Instagram rejected the request (code {error.get('code', response.status_code)}). Check token permissions and account access.")
        return data

    def pages(self, path, fields):
        params = {'fields': fields, 'limit': 100}
        while True:
            data = self.call(path, **params)
            yield from data.get('data', [])
            after = data.get('paging', {}).get('cursors', {}).get('after')
            if not data.get('paging', {}).get('next') or not after:
                break
            params['after'] = after


api = Instagram()


def sync_reels():
    if live():
        media = api.pages(os.environ['INSTAGRAM_ACCOUNT_ID'] + '/media', 'id,caption,media_product_type,permalink,timestamp')
    else:
        media = [dict(id=f'demo-{i}', caption=caption, media_product_type='REELS', permalink='', timestamp=datetime.now(timezone.utc).isoformat())
                 for i, caption in enumerate(['The little details that change everything ✨', 'Your next favorite find. A closer look.', 'A behind-the-scenes kind of day.'])]
    added = 0
    with connect() as db:
        for reel in media:
            if reel.get('media_product_type') != 'REELS':
                continue
            cursor = db.execute('INSERT OR IGNORE INTO reels(id,caption,url,timestamp) VALUES (?,?,?,?)',
                                (reel['id'], reel.get('caption', 'Untitled reel'), reel.get('permalink', ''), reel.get('timestamp', '')))
            added += cursor.rowcount
        db.execute("UPDATE settings SET value=? WHERE key='last_sync'", (datetime.now(timezone.utc).isoformat(),))
    if added:
        event(f'{added} new reel(s) discovered. Configure a rule to activate.')
    return added


def record(comment, reel, status, detail):
    with connect() as db:
        db.execute('INSERT INTO actions(comment_id,reel_id,username,comment,status,detail) VALUES (?,?,?,?,?,?) ON CONFLICT(comment_id) DO UPDATE SET status=excluded.status, detail=excluded.detail, updated=CURRENT_TIMESTAMP',
                   (comment['id'], reel['id'], comment.get('username', 'Instagram user'), comment.get('text', ''), status, detail))


def matches(text, keywords):
    return any(re.search(r'(?<!\w)' + re.escape(k.strip()) + r'(?!\w)', text, re.I) for k in keywords.split(',') if k.strip())


def process_comment(reel, comment):
    if not matches(comment.get('text', ''), reel['keywords']):
        return
    if live() and str(comment.get('from', {}).get('id', '')) == os.environ['INSTAGRAM_ACCOUNT_ID']:
        return
    with connect() as db:
        previous = db.execute('SELECT status FROM actions WHERE comment_id=?', (comment['id'],)).fetchone()
    if previous:  # Persisted attempts are never automatically resent, even after a timeout.
        return
    replies = list(api.pages(comment['id'] + '/replies', 'id,text,from')) if live() else comment.get('replies', [])
    owner = os.environ['INSTAGRAM_ACCOUNT_ID'] if live() else 'demo-owner'
    if any(str(r.get('from', {}).get('id')) == owner and r.get('text', '').strip() == reel['reply'].strip() for r in replies):
        record(comment, reel, 'skipped', 'Your custom comment reply already exists. No DM sent.')
        return
    if live():
        timestamp = comment.get('timestamp')
        if not timestamp:
            record(comment, reel, 'skipped', 'Comment timestamp unavailable; cannot verify private reply window.')
            return
        if datetime.fromisoformat(timestamp.replace('Z', '+00:00')) < datetime.now(timezone.utc) - timedelta(days=7):
            record(comment, reel, 'skipped', 'Comment is outside the private reply window.')
            return
    record(comment, reel, 'sending', 'DM attempt reserved. Automatic retries disabled to prevent duplicates.')
    try:
        if live():
            api.call(owner + '/messages', 'POST', recipient={'comment_id': comment['id']}, message={'text': reel['dm']})
        record(comment, reel, 'dm_sent', 'DM sent. Posting comment reply next.')
        if live():
            api.call(comment['id'] + '/replies', 'POST', message=reel['reply'])
        record(comment, reel, 'completed', 'DM and comment reply sent.' if live() else 'Demo: DM and comment reply simulated.')
    except RuntimeError as exc:
        record(comment, reel, 'review', str(exc) + ' Review in Instagram before taking further action.')


def run_automation():
    if not run_lock.acquire(blocking=False):
        return {'message': 'A run is already in progress.'}
    try:
        sync_reels()
        with connect() as db:
            reels = db.execute("SELECT * FROM reels WHERE enabled=1 AND (id LIKE 'demo-%') = ?", (int(not live()),)).fetchall()
        for reel in reels:
            comments = api.pages(reel['id'] + '/comments', 'id,text,username,from,timestamp') if live() else [
                dict(id=reel['id'] + '-a', username='sarah.creates', text='Love this! Send me the link ✨'),
                dict(id=reel['id'] + '-b', username='alex.studio', text='Can I get more info?', replies=[{'text': reel['reply'], 'from': {'id': 'demo-owner'}}]),
                dict(id=reel['id'] + '-c', username='mira.daily', text='Info please!')]
            for comment in comments:
                process_comment(reel, comment)
        event(f"{'Live' if live() else 'Demo'} run completed · {len(reels)} active rule(s).")
        return {'message': f'Run completed. Checked {len(reels)} active rule(s).'}
    finally:
        run_lock.release()


@app.before_request
def protect_mutations():
    if request.method == 'POST' and not secrets.compare_digest(request.headers.get('X-CSRF-Token', ''), session.get('csrf', secrets.token_hex(32))):
        return jsonify(error='Refresh the dashboard and try again.'), 403


@app.errorhandler(RuntimeError)
def operational_error(error):
    return jsonify(error=str(error)), 502


@app.get('/')
def index():
    session.setdefault('csrf', secrets.token_hex(32))
    return render_template('index.html', csrf=session['csrf'])


@app.get('/api/state')
def state():
    with connect() as db:
        return jsonify(mode='live' if live() else 'demo', background=setting('background') == '1', last_sync=setting('last_sync'),
                       reels=[dict(r) for r in db.execute("SELECT * FROM reels WHERE (id LIKE 'demo-%') = ? ORDER BY timestamp DESC", (int(not live()),))],
                       actions=[dict(r) for r in db.execute("SELECT * FROM actions WHERE (reel_id LIKE 'demo-%') = ? ORDER BY updated DESC LIMIT 100", (int(not live()),))],
                       events=[dict(r) for r in db.execute('SELECT * FROM events ORDER BY id DESC LIMIT 10')])


@app.post('/api/sync')
def sync():
    if not run_lock.acquire(blocking=False):
        return jsonify(error='A run is in progress. Try again shortly.'), 409
    try:
        return jsonify(message=f'Discovered {sync_reels()} new reel(s).')
    finally:
        run_lock.release()


@app.get('/api/reels/<reel_id>/analytics')
def reel_analytics(reel_id):
    with connect() as db:
        reel = db.execute("SELECT * FROM reels WHERE id=? AND (id LIKE 'demo-%') = ?", (reel_id, int(not live()))).fetchone()
        if not reel:
            return jsonify(error='Reel not found.'), 404
        automation = {r['status']: r['count'] for r in db.execute('SELECT status, COUNT(*) AS count FROM actions WHERE reel_id=? GROUP BY status', (reel_id,))}
    key = (live(), reel_id)
    with analytics_lock:
        cached = analytics_cache.get(key)
    if cached and time.monotonic() - cached[0] < 60:
        result = dict(cached[1])
    else:
        metrics = dict.fromkeys(['views', 'reach', 'likes', 'comments', 'saved', 'shares'])
        notes = []
        if not live():
            metrics.update(views=12480, reach=8620, likes=734, comments=92, saved=126, shares=58)
            notes.append('Sample analytics for demonstration only.')
            readable_comments = 3
        else:
            metadata = api.call(reel_id, fields='id,like_count,comments_count')
            metrics.update(likes=metadata.get('like_count'), comments=metadata.get('comments_count'))
            def insight(name):
                try:
                    response = api.call(reel_id + '/insights', metric=name)
                    entries = response.get('data', [])
                    if not entries:
                        return name, None
                    entry = entries[0]
                    value = entry.get('total_value', {}).get('value')
                    if value is None and entry.get('values'):
                        value = entry['values'][-1].get('value')
                    return name, value if isinstance(value, (int, float)) else None
                except RuntimeError:
                    return name, None
            with ThreadPoolExecutor(max_workers=4) as pool:
                for name, value in pool.map(insight, ['views', 'reach', 'saved', 'shares']):
                    metrics[name] = value
            try:
                readable_comments = sum(1 for _ in api.pages(reel_id + '/comments', 'id'))
            except RuntimeError:
                readable_comments = None
            if any(value is None for value in metrics.values()):
                notes.append('Some metrics are unavailable. Check instagram_business_manage_insights permission, token access, and metric availability for this reel. Unavailable values are not zero.')
            if metrics['comments'] and readable_comments == 0:
                notes.append('Instagram reports comments but returns none to this app. Development mode or app access restrictions may prevent automation from reading these comments. Check app roles and permission access in Meta.')
        result = dict(metrics=metrics, readable_comments=readable_comments, notes=notes,
                      fetched_at=datetime.now(timezone.utc).isoformat(), mode='live' if live() else 'demo')
        with analytics_lock:
            analytics_cache[key] = (time.monotonic(), result)
    result['automation'] = dict(dm_sent=sum(automation.get(s, 0) for s in ['completed', 'dm_sent']),
                                completed=automation.get('completed', 0), skipped=automation.get('skipped', 0),
                                review=automation.get('review', 0) + automation.get('sending', 0))
    return jsonify(result)


@app.post('/api/reels/<reel_id>')
def save_rule(reel_id):
    data = request.get_json(silent=True) or {}
    for field, limit in [('keywords', 500), ('reply', 1000), ('dm', 1000)]:
        if not isinstance(data.get(field), str) or not data[field].strip() or len(data[field]) > limit:
            return jsonify(error=f'{field} is required (maximum {limit} characters).'), 400
    if not any(k.strip() for k in data['keywords'].split(',')):
        return jsonify(error='Enter at least one keyword.'), 400
    with connect() as db:
        cursor = db.execute('UPDATE reels SET keywords=?,reply=?,dm=?,enabled=? WHERE id=?',
                           (data['keywords'].strip(), data['reply'].strip(), data['dm'].strip(), int(bool(data.get('enabled'))), reel_id))
        if not cursor.rowcount:
            return jsonify(error='Reel not found.'), 404
    return jsonify(message='Automation rule saved.')


@app.post('/api/run')
def run():
    return jsonify(run_automation())


@app.post('/api/background')
def background():
    enabled = bool((request.get_json(silent=True) or {}).get('enabled'))
    with connect() as db:
        db.execute("UPDATE settings SET value=? WHERE key='background'", ('1' if enabled else '0',))
    event('Background automation ' + ('enabled.' if enabled else 'paused.'))
    return jsonify(message='Background automation ' + ('enabled.' if enabled else 'paused.'))


def worker():
    while True:
        try:
            if setting('background') == '1':
                run_automation()
        except Exception as exc:
            event('Background run failed: ' + (str(exc) if isinstance(exc, RuntimeError) else 'Unexpected error. Check server logs.'))
            app.logger.exception('Background run failed')
        threading.Event().wait(max(15, int(os.getenv('POLL_SECONDS', '60'))))


init_db()
if not live():
    sync_reels()

if __name__ == '__main__':
    from waitress import serve
    threading.Thread(target=worker, daemon=True).start()
    print('ReelFlow is ready at http://127.0.0.1:' + os.getenv('PORT', '5000'))
    serve(app, host='127.0.0.1', port=int(os.getenv('PORT', '5000')), threads=8)
