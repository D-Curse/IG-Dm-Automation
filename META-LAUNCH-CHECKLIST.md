# DM-Automation: Meta launch configuration

Prepared 10 October 2026 for the current single-account Flask app. The attached screenshots show Development mode, no configured domain, a blank general authorize callback, and v26.0 dashboard upgrade selections. The app currently defaults to v25.0. The screenshots do not show permission approval status.

## Policy pages to publish

The HTML files in `static/legal/` can be hosted as a static folder on a public HTTPS website. Keep `legal.css` beside them. No Flask deployment is required to publish these documents.

| Meta field | Public URL path to use on your chosen host |
| --- | --- |
| Privacy Policy URL | `/privacy-policy.html` |
| Terms of Service URL | `/terms-of-service.html` |
| User data deletion: instructions URL | `/data-deletion.html` |

These paths assume you publish the contents of `static/legal` at your site's root. If you host that folder under another path, use the actual full URLs. Local previews are `/static/legal/privacy-policy.html`, `/static/legal/terms-of-service.html`, and `/static/legal/data-deletion.html` on the Flask app. **A localhost URL cannot serve as a publicly reachable policy URL for Meta.**

Contact supplied: `dhruvbhatada@gmail.com`. The documents identify the operator as the operator of DM-Automation; replace this description with your full legal/business identity and any legally required address before public release. They are drafts tailored to the current implementation, not certification of legal compliance. Review the accuracy of your actual deployment, providers, retention practices, jurisdiction-specific notices, and ability to fulfill deletion requests before publishing.

## Meta console configuration

1. In Settings → Basic, complete the display name `DM-Automation`, support/contact email, required app icon/category fields, privacy URL, terms URL, and user data deletion instructions URL. Add your actual website domain where required by the selected product/login flow.
2. Use **Instagram API with Instagram Login** for this implementation (`graph.instagram.com`). Do not mix permissions or tokens from the Facebook Login flow.
3. Review access for `instagram_business_basic`, `instagram_business_manage_comments`, `instagram_business_manage_messages`, and `instagram_business_manage_insights`. Request only features the app uses. Follow the product dashboard's App Review, Advanced Access, business verification, and testing requirements for the accounts and users you intend to serve. Switching the mode to Live is separate from approval/access for individual permissions.
4. In Development mode, test within the permitted app-role/test-account setup, with invitations accepted. Confirm that the commenter and connected account satisfy Meta's test-access rules. The current reel reports two comments while the comments endpoint returns none; changing the Live toggle alone is not a confirmed fix for that discrepancy.
5. For review, prepare permission-specific explanations and a recording that shows connecting/authorizing an account, discovering a reel, configuring a keyword, processing a permitted comment, the resulting public/private replies, and analytics. Supply reviewer access and instructions through Meta's review flow without publicly exposing credentials.
6. Complete any verification, platform questions, and ongoing Data Use Checkup tasks shown in your dashboard. Enable Live mode after the necessary configuration and approvals are in place.

## What the current app still needs for public onboarding

- **OAuth onboarding is not implemented.** The current app uses an account ID/token supplied in `.env`. Before connecting customers, implement Instagram authorization, state/CSRF validation, the actual callback route, token exchange, and token renewal/revocation. Register the exact HTTPS redirect URL in the Instagram product's OAuth settings. Do not put an invented URL in the blank callback field in your screenshot; the general app-authentication field is not a substitute for the product's redirect settings.
- **Public dashboard authentication is not implemented.** The current server binds to localhost and has no account login or tenant isolation. Publish only the static policy pages for now. A public dashboard needs authentication, authorization, HTTPS, secret storage, and deployment controls. Public policies do not require exposing the automation UI.
- **Automatic data deletion is not implemented.** Use Meta's data-deletion **instructions URL** option with the supplied page. Do not register this static page as a callback endpoint. If a selected Meta flow requires a callback, implement the specified signed-request verification and status response before registering one.
- **Webhooks are not implemented.** The app polls comments. A webhook configuration is needed only if you add webhook-driven processing or the product's chosen integration requires it. Then implement GET verification, POST signature verification, event deduplication, and the appropriate account subscriptions. Do not register a nonexistent webhook URL.
- **Retention and deletion are manual.** Decide on a retention schedule, enforce it, and update the policy. Build a deletion procedure covering SQLite records, relevant logs, tokens, caches, and any backups. Disable affected rules before removing duplicate history so old comments are not immediately processed again. Do not delete user data merely to make a permission test pass.
- **Single-process operation only.** Run one `python app.py` server. This starts the background worker; `flask run` alone does not. Multiple instances can race and duplicate sends. A production service needs a dedicated worker/queue and shared transactional deduplication if it scales beyond one process.
- **Operational readiness:** validate renewed token permissions, handle expiry/rate limits, test message-window restrictions, verify all links/message text, and confirm a successful end-to-end run with an eligible test account before relying on automation.

## Settings shown in your screenshots

| Setting | Guidance for this app |
| --- | --- |
| API upgrade v26.0 | `.env` controls the version in actual requests. The current default is v25.0. Check Meta's supported versions and changelog; test reads and sends before choosing v26.0. The dashboard selection alone does not change explicit version strings in this app. |
| Native/desktop app | The Flask application is a web/server app; do not enable this just because you run it on Windows. |
| Server IP / settings IP allowlist | Optional controls: use only known stable server/admin IPs. Random or changing addresses can lock out valid requests. |
| Require app secret | The current client sends bearer tokens only and does not implement app-secret proof. Implement the required proof before enabling a setting that mandates it. Never put the app secret in browser code. |
| Require 2-factor reauthorization | Consider for app administration; secure developer accounts with two-factor authentication. This is not a fix for the empty comments response. |
| Allow API access to app settings | No app feature needs to modify Meta app settings through an API. Keep off unless you implement and need that capability. |
| App Page, advertising accounts, social discovery, share redirect list | Not features used by this app. Do not add unrelated advertising accounts or redirects. Configure only if your chosen Meta product explicitly needs them. |
| Age, country, GDPR restrictions | Choose according to the audience and applicable legal obligations; do not use them to try to bypass review or comment access restrictions. |

## References and verification limit

Consult the current requirements shown in your app's dashboard and the official sources below. Meta's documentation pages returned access errors/rate limits during preparation; exact console requirements could not all be independently verified. This checklist distinguishes observed code/screenshots from conditional platform steps and is not a guarantee of Meta approval.

- Instagram API with Instagram Login: https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/
- App Review: https://developers.facebook.com/docs/app-review/
- Platform Terms: https://developers.facebook.com/terms/
- Developer Policies: https://developers.facebook.com/devpolicy/
- Data deletion callback specification (if you implement one): https://developers.facebook.com/docs/development/create-an-app/app-dashboard/data-deletion-callback/
