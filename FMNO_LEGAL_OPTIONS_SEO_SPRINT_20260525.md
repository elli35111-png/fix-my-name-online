# FMNO Legal Options SEO Sprint — 2026-05-25

## Purpose
Extend the Julian Goldie-style long-tail SEO mechanism for FixMyNameOnline™ with a new legal-options layer that captures high-intent searches around defamation, old news articles, court mentions, outdated Google snippets, publisher requests and privacy complaints.

## Live URLs shipped

Primary legal-options page:
- https://fixmynameonline.com/legal-options-for-negative-google-results

Supporting long-tail pages:
- https://fixmynameonline.com/defamation-and-google-search-results-options
- https://fixmynameonline.com/remove-old-news-article-from-google-australia
- https://fixmynameonline.com/court-mention-showing-on-google-australia
- https://fixmynameonline.com/employer-found-old-article-about-me
- https://fixmynameonline.com/google-outdated-content-removal-australia
- https://fixmynameonline.com/publisher-removal-request-for-old-article
- https://fixmynameonline.com/privacy-complaint-for-google-search-results-australia

## Website changes
- Added 8 generated SEO guides in `generated_seo_guides.json`.
- Strengthened `/learn` with a top legal-options card.
- Strengthened `/services` with Legal Options Evidence Pack positioning.
- Added legal-options triage outcome in `TRIAGE_NEXT_STEPS`.
- Added legal/defamation/privacy intake option to `/app` and `/free-search-snapshot` forms.
- Updated triage so legal/court/defamation/privacy/lawyer/publisher-request wording routes to `legal-options`.

## Compliance guardrails
- FMNO is positioned as evidence-pack/search-repair support, not a law firm.
- Pages clearly say FixMyNameOnline™ does not provide legal advice.
- No guaranteed removal, de-indexing, review-removal, ranking or platform outcomes.
- Legal/litigation/formal-demand work is framed as lawyer-review/handoff where needed.

## Verification
Commit pushed:
- `9d0d947 Add FMNO legal options SEO layer`

Live verification completed:
- New URLs returned HTTP 200 after Render deploy.
- Primary page title verified: `Legal Options for Negative Google Results — Private Evidence Review | FixMyNameOnline™`
- Primary page canonical verified.
- Legal disclaimer verified on primary page.
- Sitemap verified with 217 URLs.
- Sitemap contains all 8 new URLs.
- Robots verified: allows crawling and points to `https://fixmynameonline.com/sitemap.xml`.

## Discovery push
IndexNow JSON POST submitted for 11 URLs:
- 8 new guide URLs
- `/learn`
- `/services`
- `/sitemap.xml`

Results:
- `https://api.indexnow.org/indexnow` returned HTTP 200
- `https://www.bing.com/indexnow` returned HTTP 200

## Distinction
IndexNow HTTP 200 means discovery/submission accepted. It does not prove Google or Bing indexed/ranked the pages yet. Ranking/indexing must be monitored separately.
