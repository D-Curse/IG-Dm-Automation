"""Read-only diagnostics. Never prints credentials or comment bodies."""
import os
import app

try:
    permissions = app.api.call(os.environ['INSTAGRAM_ACCOUNT_ID'] + '/permissions')
    print('permissions:', permissions)
except RuntimeError as exc:
    print('permissions_check:', str(exc))

with app.connect() as db:
    reels = db.execute("SELECT * FROM reels WHERE enabled=1 AND id NOT LIKE 'demo-%'").fetchall()
for reel in reels:
    print('media_metadata:', app.api.call(reel['id'], fields='id,permalink,comments_count,media_product_type'))
    comments = list(app.api.pages(reel['id'] + '/comments', 'id,text,username,from,timestamp'))
    print('reel:', reel['id'], 'comments:', len(comments))
    for comment in comments:
        print({'comment_id': comment['id'],
               'keyword_match': app.matches(comment.get('text', ''), reel['keywords']),
               'is_owner': str(comment.get('from', {}).get('id', '')) == os.environ['INSTAGRAM_ACCOUNT_ID'],
               'has_timestamp': bool(comment.get('timestamp'))})
    minimal = app.api.call(reel['id'] + '/comments', fields='id,text', limit=100)
    print('minimal_fields_comment_count:', len(minimal.get('data', [])))
    print('response_keys:', list(minimal.keys()))
