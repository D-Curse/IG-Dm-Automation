# Deploy DM-Automation legal pages to Vercel

This repository is a static HTML/CSS site. No Python, Flask, Node dependencies, or framework are needed for hosting the legal pages.

1. In Vercel, import `D-Curse/IG-Dm-Automation` from GitHub.
2. Select the intended team and project name.
3. Set Framework Preset to **Other** and Root Directory to the repository root (`./`).
4. The committed `vercel.json` sets Output Directory to `static/legal` and disables the build command. If old project overrides exist, clear them or match these settings. No install command or environment variables are needed.
5. Deploy. Ensure the production policy URLs are accessible without Vercel Authentication or other deployment protection, so Meta and users can read them.

After deployment, use the actual production hostname:

- `https://YOUR-PROJECT.vercel.app/privacy-policy`
- `https://YOUR-PROJECT.vercel.app/terms-of-service`
- `https://YOUR-PROJECT.vercel.app/data-deletion`

The homepage links to all three pages. `cleanUrls` provides extension-free paths; existing `.html` links redirect to their clean equivalents on Vercel. The stylesheet is available at `/legal.css`.

Only `static/legal` is served. `.gitignore` excludes the local Flask app from the repository, and `.vercelignore` excludes it from direct CLI uploads. Do not upload `.env`, access tokens, SQLite databases, or the private dashboard. The policy site requires no Instagram credentials.

The documents remain drafts requiring operator/legal review before submission. Hosting does not grant Meta permissions or approval. No Vercel project or production deployment is created by adding this configuration.
