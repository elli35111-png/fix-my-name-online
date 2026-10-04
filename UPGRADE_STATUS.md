# FMNO simple self-service release (v53)

## Scope

Free self-service desk plus US$19 one-time Single Action for one fixed URL. No new subscriptions, multi-link packages, consultations, human review or owner fulfilment queue for new purchases. Customers check facts and submit their own requests. Saved drafts/notes, text/JSON export, imported calendar reminders, lost-link recovery and eligible seven-day unused-purchase refunds are included. Mandatory billing/privacy/fault obligations remain.

Legacy purchases and billing access remain supported. New NameWatch sales are paused; its historical records are not cancelled or deleted. Old managed-offer website checkouts do not take new payments.

## Verification before publication

- 98 tests pass, including synthetic Stripe exact-price/status verification, one-URL limits, legacy access, CSRF and cross-workspace isolation, persistence, exports, calendar, recovery throttling, refund idempotency/race protection and mobile browser flows.
- Three JavaScript syntax checks, Python compilation and `git diff --check` pass.
- Synthetic tests do not establish a real paid transaction, actual refund, customer cancellation or delivered email.
- Screenshots are local QA artefacts excluded from Git. Independent image-review tooling failed authentication; browser functional/responsive checks completed.
- Original dirty `/Users/ellicakar/fix_my_name_online` rebuild was not incorporated; this release is based on production commit `0daba59e67746859bc8d94de7bfbf506a668a038` in a separate worktree.

## Billing

Isolated FMNO account: `acct_1TsYh19eHjBZ9fNn`.
Single price `price_1UMckV9eHjBZ9fNnGlAxt9PY` verified active, USD 1900, one-time.
Unused new pack price `price_1UMckV9eHjBZ9fNnQlnDedvp` archived and read back inactive; legacy one-URL price preserved.
Portal `bpc_1UMckW9eHjBZ9fNnw4y90p5Y` verified active with email login, invoice history, payment-method updates and period-end cancellation, no proration or subscription upgrades.
No live charge/refund performed.

## Data and hosting

Service `srv-d7s3ja77f7vs73dcb420`, main branch, Starter plan, existing 1GB persistent disk mounted at `/var/data`.
Application data: `/var/data/fmno` (0700). Ten enquiries, ten private rooms, ten fulfilment cases and ten queue items were preserved and checksummed before release.
A complete fresh archive was captured and validated at `/Users/ellicakar/.hermes/state/fmno_backups/pre-v53-20261004T004737Z.tar.gz` (0600).
Archive SHA-256: `c7a476faf66c165b846cd1428799cb43f2f2fca80d7bd6aed88ad0dc24834238`.
Protected manifest: `/Users/ellicakar/.hermes/state/fmno_backups/pre-v53-manifest.json`.

Render injects `GUNICORN_CMD_ARGS` including `--access-logfile -`; merely omitting access logging from the start command does NOT disable it. Explicitly override with `--access-logfile /dev/null` to keep bearer query strings out of Gunicorn access logs. Do not replace any existing disk.

## Publication acceptance

Expected `/health` marker: `launch-v53-simple-self-service`.
After deploy: verify public pages, actual US$19 unpaid checkout session/price/account, refused unpaid workspace access, data continuity and temporary SSH key removal. Store the final production proof outside the repo so it does not trigger a second deploy. No real customer data or payment is needed for smoke testing.
