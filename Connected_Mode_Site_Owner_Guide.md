# Site Owner Guide
## Connecting Your Website to SEO & GEO Auditor

This guide is for the site owner — the person who owns the website, Google Search Console (GSC), and Google Analytics 4 (GA4).

You do not need Google Cloud Console. You do not create API keys or OAuth clients. The tool operator (person who runs the auditor app) handles that in their own Google Cloud project.

Your job: set up GSC and GA4 correctly, then sign in once when the tool operator asks you to approve read-only access.

---

## How the two roles work together

| | Site owner (you) | Tool operator |
|---|------------------|---------------|
| Owns the website | Yes | No |
| Owns GSC + GA4 | Yes | No |
| Google Cloud project | Not needed | Creates and manages one |
| OAuth sign-in | You sign in with your Google account | Runs the setup script; may sign in as you or ask you to |
| What you share | Exact GSC property URL + GA4 Property ID | Nothing secret — just confirm access works |

The auditor reads your GSC/GA4 data as you, after you approve it. The tool never needs access to a “site owner Google Cloud project” — because you don't need one.

---

## Part 1 — Google Search Console

### Step 1 — Add and verify your property

1. Go to [Google Search Console](https://search.google.com/search-console).
2. Click Add property.
3. Choose URL prefix (most common), e.g. `https://www.yourdomain.com/`.
4. Verify ownership using a method Google offers (HTML file, DNS record, Google Analytics, etc.).
5. When verified, open the property dropdown and copy the exact URL shown (including `https://`, `www` or not, and trailing `/`). Send this to your tool operator.

Example: `https://www.example.com/` — every character must match in the auditor config.

### Step 2 — Submit a sitemap

1. Publish a real `sitemap.xml` on your site (XML file, not your homepage).
2. In GSC → Sitemaps (under Indexing).
3. Enter the sitemap path, e.g. `sitemap.xml`, and click Submit.
4. Do not submit your homepage URL as the sitemap.

### Step 3 — Request indexing (if needed)

If GSC shows pages as not indexed:

1. Use URL Inspection at the top of GSC.
2. Enter your homepage URL.
3. Click Request indexing (if offered).

Indexing can take days or weeks for new sites.

---

## Part 2 — Google Analytics 4

### Step 1 — Create or confirm your GA4 property

1. Go to [Google Analytics](https://analytics.google.com/).
2. Admin (gear) → create a Property if you don't have one.
3. Add a Web data stream for your live site URL.

### Step 2 — Install the tracking tag

1. In Admin → Data streams → your web stream → View tag instructions.
2. Add the GA4 tag to your live site (CMS, Google Tag Manager, or site code).
3. Confirm data: Reports snapshot should show sessions within 24–48 hours.

### Step 3 — Share your Property ID

1. Admin → Property settings.
2. Copy the numeric Property ID (e.g. `123456789`).
3. Send it to your tool operator.

Note: This is not the Measurement ID (`G-XXXXXXXX`). The auditor needs the numeric Property ID only.

---

## Part 3 — OAuth sign-in (one time)

The tool operator will run a setup script on their computer. It opens a browser and asks you to:

1. Sign in with the same Google account that owns GSC and GA4 (or has Full access).
2. Approve read-only access to Search Console and Analytics.

You are not giving access to Google Cloud. You are only allowing the auditor app (registered in the tool operator's project) to read your search and analytics data.

To revoke later: [Google Account → Security → Third-party access](https://myaccount.google.com/permissions).

---

## Part 4 — What the auditor checks with your data

When connected, these SEO checks use your Google data:

| Check | Needs |
|-------|--------|
| Sitemap submission status in GSC | GSC property |
| Crawl / index status (URL Inspection) | GSC property |
| Click-through rate (CTR) | GSC Performance data (needs impressions) |
| Dwell time, bounce rate, pogo-sticking | GA4 sessions on your site |

If the site is new or not indexed, CTR may show Not Meeting with zero impressions — that is normal until Google shows search traffic in GSC.

If GA4 has no sessions yet, the three GA4 rows stay Manual until the tracking tag collects data.

---

## Site owner checklist

- [ ] GSC property verified; exact property URL sent to tool operator  
- [ ] Valid `sitemap.xml` live and submitted in GSC  
- [ ] GA4 property created; tracking tag on live site  
- [ ] Numeric GA4 Property ID sent to tool operator  
- [ ] Completed OAuth browser sign-in when tool operator requested it  
- [ ] Same Google account used for GSC, GA4, and OAuth  

---

## What you do NOT need to do

- Create a Google Cloud project  
- Enable APIs in Cloud Console  
- Create API keys or OAuth clients  
- Share Google Cloud credentials  
- Give anyone access to a “site owner GCP project”  

That is all handled by the tool operator in their Cloud project.

---

*Site Owner Guide — SEO & GEO Auditor Connected Mode. See Connected_Mode_Tool_Operator_Guide.pdf for the technical setup on the auditor side.*
