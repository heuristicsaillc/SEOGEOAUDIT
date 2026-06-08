# Tool Operator Guide
## Google Cloud + OAuth Setup for SEO & GEO Auditor

This guide is for the tool operator — the person who installs and runs the SEO & GEO Auditor app on a server or laptop.

You create one Google Cloud project (yours, not the site owner's). That project holds the APIs, OAuth app, and PageSpeed API key. The site owner never shares their Cloud project; they only sign in with their Google account so the app can read their Search Console and GA4.

---

## Who owns what?

[[FLOW:roles]]

- You do not get access to the site owner's Google Cloud — they don't need one.  
- They do not get access to your Google Cloud — they only approve OAuth read access to GSC/GA4.  
- One your Cloud project can connect many client sites (each row in `connected_properties.json`).

---

## Part 1 — Create your Google Cloud project

1. Sign in to [Google Cloud Console](https://console.cloud.google.com/) with your Google account (operator account).
2. Project dropdown → New project.
3. Name it (e.g. `SEO GEO Auditor`).
4. Click Create. Note the Project ID (e.g. `seo-geo-auditor-123456`).

Enable billing only if Google prompts you. Typical audit usage stays within free tiers.

---

## Part 2 — Enable APIs

APIs & Services → Library — enable each:

| API | Purpose |
|-----|---------|
| Google Search Console API | Sitemap status, CTR, URL Inspection |
| Google Analytics Data API | GA4 engagement metrics |
| Google Analytics Admin API | List GA4 properties during setup |
| PageSpeed Insights API | Core Web Vitals in audits |

---

## Part 3 — PageSpeed API key

OAuth does not cover PageSpeed. Create a separate API key:

1. APIs & Services → Credentials → + Create credentials → API key.
2. Copy the key into the project root `.env`:

```
GOOGLE_API_KEY=your_api_key_here
```

3. (Recommended) Restrict the key to PageSpeed Insights API only.

Restart the backend after editing `.env`.

---

## Part 4 — OAuth consent screen

1. APIs & Services → OAuth consent screen.
2. User type: External (unless internal Workspace only).
3. App name, support email, developer email → Save and continue.
4. Scopes → Add or remove scopes:
   - `https://www.googleapis.com/auth/webmasters.readonly`
   - `https://www.googleapis.com/auth/analytics.readonly`
5. If app status is Testing, add Test users: email(s) that will sign in (site owner's Gmail, or yours if you own the properties).

---

## Part 5 — OAuth Desktop client

1. Credentials → + Create credentials → OAuth client ID.
2. Type: Desktop app.
3. Download JSON → save as:

```
secrets/google-oauth-client.json
```

Never commit this file (it is git-ignored).

---

## Part 6 — Browser sign-in

From the `backend` folder:

```
cd backend
source .venv/bin/activate
pip install -r requirements.txt
python scripts/google_auth.py
```

- Browser opens → sign in with the account that has access to the client's GSC and GA4 (often the site owner's account; you can sit with them or share screen).
- Token saved to `secrets/google-oauth-token.json`.

Re-list properties without browser:

```
python scripts/google_auth.py --list-only
```

You should see GSC URLs and GA4 Property IDs. Compare with what the site owner sent you.

---

## Part 7 — Register each site

Edit `backend/connected_properties.json`:

```json
{
  "example.com": {
    "gsc_site_url": "https://www.example.com/",
    "ga4_property_id": "123456789"
  }
}
```

| Field | Rule |
|-------|------|
| Key | Hostname only, lowercase, no `www` |
| `gsc_site_url` | Exact match from GSC / `--list-only` |
| `ga4_property_id` | Numeric only |

Restart the backend. Run a test audit; confirm connected and first-party GSC rows are scored.

[[FLOW:auth]]

---

## Part 8 — Verify connection

| Check | Expected |
|-------|----------|
| Audit shows connected | Yes for mapped domain |
| Sitemap GSC-submission | Scored (Meeting / Partial / Not Meeting) |
| Log file analysis | Scored when URL Inspection works |
| CTR | Scored; Not Meeting if 0 impressions is OK |
| GA4 engagement (3 rows) | Manual until GA4 has sessions |

---

## Part 9 — Troubleshooting

| Issue | Fix |
|-------|-----|
| `--list-only` shows no GSC sites | Wrong Google account; use site owner's account |
| GSC Not Measured | Check `gsc_site_url` exact match; Search Console API enabled; retry audit |
| OAuth blocked (Testing) | Add user email under OAuth consent → Test users |
| PageSpeed Not Measured | Enable PageSpeed API; set `GOOGLE_API_KEY` |
| GA4 list empty | Enable Analytics Admin API; or get Property ID from site owner manually |

---

## Tool operator checklist

- [ ] Google Cloud project created (your account)  
- [ ] Four APIs enabled  
- [ ] PageSpeed API key in `.env`  
- [ ] OAuth consent screen + scopes configured  
- [ ] Desktop OAuth client → `secrets/google-oauth-client.json`  
- [ ] `python scripts/google_auth.py` completed (site owner account if needed)  
- [ ] `connected_properties.json` updated per client site  
- [ ] Backend restarted; test audit successful  

---

## Files reference

| File | Purpose |
|------|---------|
| `secrets/google-oauth-client.json` | OAuth Desktop client (you create) |
| `secrets/google-oauth-token.json` | Token after sign-in (auto-created) |
| `backend/connected_properties.json` | Domain → GSC URL + GA4 ID |
| `.env` → `GOOGLE_API_KEY` | PageSpeed only |

---

*Tool Operator Guide — SEO & GEO Auditor. Give Connected_Mode_Site_Owner_Guide.pdf to your client for GSC, GA4, and OAuth sign-in steps.*
