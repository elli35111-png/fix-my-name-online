# FMNO Health Alert Triage and Remediation — 2026-07-21

Verified at: 2026-07-21 06:52 ACST

## Alert inspected

Apple Mail message:
- Subject: `FMNO ALERT — health issues need attention (3)`
- Received: 2026-07-20 09:07 ACST
- Source: weekly autonomous platform audit

The three flags were: Render-ephemeral JSONL storage, missing NameWatch Stripe configuration, and absent Brevo API configuration.

## Remediated — LIVE VERIFIED

### NameWatch Alert checkout

- Created a dedicated live Stripe product and USD 29/month recurring price in the isolated FMNO account `acct_1TsYh19eHjBZ9fNn`.
- Added `STRIPE_PRICE_SENTINEL` to the Render service environment and rebuilt/deployed.
- `/checkout/sentinel` now reaches Stripe Checkout.
- Verified checkout properties through the isolated account API: live mode, subscription, USD 29.00, open/unpaid, tier `sentinel`.
- No purchase or charge was made.

### Latest application deployment

- Manually deployed Git commit `6d8b5c0` on Render.
- Render reports the deployment Live.
- Production crawl: 225 sitemap URLs, 225 unique, 225 HTTP 200.
- `/health`: HTTP 200.
- Fake URL: HTTP 404.
- Local regression suite with Stripe variables intentionally removed: 23 passed.

### Backup/watchdog mitigation

- Upgraded `~/.hermes/scripts/fmno_alert_watchdog.py` so every five-minute authenticated poll now saves:
  - a private rolling full export at `~/.hermes/state/fmno_backups/latest.json`;
  - a timestamped, content-hashed backup whenever records change.
- Backup directory mode: `0700`; backup files: `0600`.
- Watchdog execution verified successfully.
- The weekly audit instructions now require distinguishing synthetic QA rows from real customers and checking these local archives before alleging data loss.

## Corrected finding — no proven customer loss

The historical snapshot rows found in the watchdog/email evidence were synthetic operator tests, including `FMNO Watchdog Live Verification` and `Hermes Safari QA Test — Ignore/Delete`. The report itself also stated there were no real customer leads or paid-customer events. The observed count reset proves the filesystem is ephemeral, but it does not prove that a real customer record was lost.

## Remaining — MITIGATED / PENDING

### Persistent server-side storage

- Render service is on the Free plan and has no persistent disk.
- Current mitigation: authenticated five-minute local private backup plus email alerts.
- Durable server-side storage still requires a paid Render persistent disk or an external managed database. No paid upgrade was performed.

### Brevo

- Live `/health` still reports `brevo_email_configured: false` because no usable Brevo API key is stored in the FMNO Render environment/local credentials.
- Lead and paid-event alerting is not absent: the proven Apple Mail watchdog is active every five minutes and last status is OK.
- No fake or unverified Brevo credential was added.

## Final status

- Immediate revenue blocker: FIXED.
- FMNO live availability and sitemap: VERIFIED.
- Alerting: ACTIVE through Apple Mail fallback.
- Customer-data loss: NOT PROVEN; historical missing rows were synthetic QA.
- Long-term persistence: still architectural work, currently mitigated but not fully resolved.
