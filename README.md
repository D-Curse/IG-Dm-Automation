# ReelFlow

A Flask dashboard for Instagram reel comment-to-DM automation. Includes keyword rules per reel, custom comment replies and DMs, manual runs, background polling, persistent SQLite history, and an interactive demo.

## Run on Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python app.py
```

Open http://127.0.0.1:5000. Instagram credentials are not needed for demo mode; dashboard login setup is still required. Configure a sample reel, enable its rule, and click **Start automation**. Two sample comments receive simulated messages; one already-replied comment is skipped. Repeated runs do not resend messages.

## Dashboard login

Before accessing the dashboard, run `.\.venv\Scripts\python setup_login.py` in your terminal. Enter a username and a password/passphrase of at least 14 characters. Password input is hidden and only a salted scrypt hash is stored in `instance/dashboard-auth.json`. There is no default login or public signup. Until configured, dashboard and API access are denied. Run the same command to reset credentials; existing sessions become invalid without restarting.

Sign in at `/login`. Sessions expire after 30 minutes without dashboard interactions and after eight hours maximum; polling does not keep them alive. Sign out revokes the session on the server. Login attempts are limited to five per IP per 15 minutes, with a global ceiling of 50; this single-process limiter uses the direct client IP and does not trust forwarded headers. Policy pages remain public. Authentication does not stop background automation.

The server generates a persistent signing key in `instance/session-secret`; protect this file and the entire instance folder with OS access permissions. It replaces the legacy `SECRET_KEY` value for session signing. For HTTPS deployment set `COOKIE_SECURE=1`, and configure HTTPS before exposing the app. Keep one process and do not enable debug mode. Multi-user authorization, OAuth onboarding, and trusted reverse-proxy configuration are separate work.

## Connect Instagram

1. Use a Business or Creator account and a Meta developer app configured for **Instagram API with Instagram Login**.
2. Obtain an Instagram user access token with `instagram_business_basic`, `instagram_business_manage_comments`, and `instagram_business_manage_messages`. Access beyond app roles can require app review and Advanced Access. Follow [Meta's setup instructions](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login).
3. Copy `.env.example` to `.env`. Set `INSTAGRAM_ACCOUNT_ID`, `INSTAGRAM_ACCESS_TOKEN`, and a random `SECRET_KEY`. The API version is configurable; verify it against the version supported by your Meta app.
4. Restart, click **Sync reels**, and configure each reel. Newly discovered reels are disabled by default, so you can set the appropriate message before enabling them.

The app calls the media, comments, comment replies, and private messages endpoints at `graph.instagram.com`. It paginates results, checks comment age before private replies, and never exposes the token in the dashboard. Live delivery requires valid credentials and Meta permissions; it has not been verified against a connected account here.

## Automation behavior

- Comma-separated keywords match whole words or phrases, without case sensitivity.
- For each matching top-level comment, fetch its replies. If **your account** already posted the configured public reply (ignoring leading/trailing whitespace), record a skip and do not send a DM.
- Otherwise reserve the attempt, send the private reply using the comment ID, then post the public comment reply. A newly posted reply does not suppress the DM in the same run.
- History is persistent per comment, across runs, restarts, and rule edits. A second comment by the same person is a separate trigger. The guard applies to the triggering comment, not all comments by that person.
- Every send attempt is reserved before the network request. Failed or uncertain attempts require review in Instagram and are never automatically retried. This favors avoiding duplicate DMs over automatic delivery recovery. A public-reply failure after a successful DM also requires manual review.
- Comments older than seven days, or without a timestamp, are skipped for private replies. The platform may impose additional eligibility and rate limits.
- Demo and live reel rules are separated. Demo artwork is decorative; live reel links open the actual Instagram reel.

## Reel analytics

Click **View analytics** on a reel for lifetime views, reach, likes, comments, saves, and shares, plus this app's automation totals. Instagram results are cached for 60 seconds; refresh after that interval to fetch a new snapshot. Missing or permission-restricted metrics display as unavailable, never as zero. Insight requests use `instagram_business_manage_insights`; authorize that permission and renew your token if needed. This feature only reads analytics and does not send messages. Development mode and access restrictions may limit the comments visible to the app even when the reel's comment count is positive; the analytics panel flags this discrepancy.

## Background operation

Enable **Background automation** to poll every `POLL_SECONDS` (default 60, minimum 15). It discovers reels and processes enabled rules while `python app.py` is running. The dashboard can be closed. The computer must stay awake and the server process must stay running.

For operation after login, create a Windows Task Scheduler task with program `E:\DmAutomation\.venv\Scripts\python.exe`, argument `E:\DmAutomation\app.py`, and start directory `E:\DmAutomation`. Configure restart on failure as needed. This repository does not install a system task automatically.

Run a **single app process** through `python app.py`; it starts the worker and Waitress. The in-process lock serializes manual and scheduled runs. Importing `app:app` in another WSGI server does not start the worker. Multiple processes or replicas are not supported. The dashboard binds to localhost and has dashboard authentication and CSRF protection; configure HTTPS and deployment access controls before exposing it beyond your computer.

SQLite state is stored in `instance/automation.db`. Keep it to preserve duplicate protection. Back up this file before moving the app. Connection tokens require renewal according to Meta's token lifecycle.

## Tests

```powershell
.\.venv\Scripts\python -m unittest discover -s tests -v
```
