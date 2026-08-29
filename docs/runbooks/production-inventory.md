# Production inventory

This inventory records ownership roles and lookup locations only. It must never contain credentials, tokens, connection strings, personal email addresses, or unverified external project identifiers. Named operators and emergency phone details belong in the team's access-controlled contact roster, not in Git.

## External systems

| System | Accountable owner | Authoritative location and lookup procedure |
| --- | --- | --- |
| Vercel project | Web production operator | Open the Vercel dashboard project connected to this repository and verify **Settings → General** and **Settings → Environment Variables**. If the checkout has been linked, `.vercel/project.json` is a local lookup aid only and must not be committed. The project name and ID are intentionally not guessed here. |
| Supabase project | Data/platform operator | Open the Supabase dashboard project used by the production Vercel deployment and verify **Project Settings → General** and **Database**. Resolve the project reference from the dashboard at launch time; do not copy it or a connection URL into this file. |
| Resend domain | Email delivery operator | In Resend **Domains**, verify `aivizens.com` is the production domain and that its DNS checks pass. In the sending configuration, verify the sender is `AIVIZENS 趋势 <aivizens.daily@aivizens.com>`. |
| Gmail digest account | Content-ingestion operator | The exact mailbox is held in the Mac Mini secret store under `AI_GMAIL_IMAP_USER`; its app password is stored separately under `AI_GMAIL_IMAP_PASSWORD`. Manage both through Google Account security and verify read-only ingestion without recording the account identity here. |
| Feishu webhook | Incident-response operator | Find the production alert bot in the private Feishu operations group and confirm its webhook is installed on the Mac Mini as `FEISHU_WEBHOOK_URL`. The URL must never be pasted into tickets, logs, or this repository. |

## Mac Mini runtime

| Item | Owner | Location / procedure |
| --- | --- | --- |
| Repository | Mac Mini operator | Canonical operational default: `$HOME/nev-brief` (equivalently `/Users/<operator>/nev-brief`). Confirm the resolved `PROJECT_ROOT` before installation or recovery; a different path must be supplied explicitly. |
| Secret environment | Mac Mini operator | `$PROJECT_ROOT/.env`, mode `0600`, populated from the key contract below. Never print the file or its values during verification. |
| Current AIVIZENS schedule | Mac Mini operator | launchd label `com.aivizens.ai-daily`; template `ops/launchd/com.aivizens.ai-daily.plist`; installed plist `$HOME/Library/LaunchAgents/com.aivizens.ai-daily.plist`. |
| Retained NEV schedule | Mac Mini operator | launchd label `com.nev.daily`; template `ops/launchd/com.nev.daily.plist`. Phase 0 retains this code and schedule contract. |
| Logs | Mac Mini operator | `$PROJECT_ROOT/logs/`; AIVIZENS dated run logs use `ai-daily-YYYYMMDD.log`, with launchd stdout/stderr in `ai-daily.out.log` and `ai-daily.err.log`. NEV logs remain in the same directory during Phase 0. |

## Environment key contract

Values live only in the relevant provider secret store, Vercel Production environment, or the Mac Mini `.env`. Public URLs and the approved sender identity may use the safe samples in the example files.

| Scope | Key names | Purpose |
| --- | --- | --- |
| Supabase/Postgres | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL` | API access and direct database access. |
| DeepSeek | `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL`, `DEEPSEEK_MODEL_AI` | Model authentication, endpoint, and model selection. |
| Qwen | `QWEN_API_KEY`, `QWEN_BASE_URL`, `QWEN_MODEL` | Image-selection model access and configuration. |
| Resend | `RESEND_API_KEY`, `RESEND_FROM_EMAIL`, `RESEND_FROM_NAME`, `RESEND_FROM_EMAIL_AI`, `RESEND_FROM_NAME_AI` | Email API access and approved sender identity. |
| Gmail IMAP | `AI_DIGEST_SENDER`, `AI_GMAIL_IMAP_HOST`, `AI_GMAIL_IMAP_USER`, `AI_GMAIL_IMAP_PASSWORD`, `AI_IMAP_PROXY` | Digest mailbox selection and network access. |
| AI assets/delivery | `AI_IMAGE_BUCKET`, `AI_EMAIL_SEND_ENABLED` | Image storage and the explicit Resend send kill switch. Delivery idempotency is fixed as `aivizens-{brief_date}-{subscriber_id}`. |
| Web | `WEB_BASE_URL`, `NEXT_PUBLIC_WEB_BASE_URL` | Server-side and browser-visible canonical web origins. |
| Subscription abuse limit | `SUBSCRIPTION_HASH_SECRET` | Server-only HMAC key for the AI subscription rate limiter. |
| Monitoring/admin | `FEISHU_WEBHOOK_URL`, `SENTRY_DSN`, `HEALTHCHECKS_PING_URL`, `ADMIN_TOKEN` | Alerts, error reporting, health pings, and admin authentication. |
| Runtime behavior | `CRAWL_MAX_QPS_PER_DOMAIN`, `LOG_LEVEL`, `RSSHUB_BASE_URL` | Crawl rate, logging level, and RSSHub endpoint. |
| Proxy fallback | `HTTPS_PROXY`, `HTTP_PROXY` | Optional IMAP proxy fallback when `AI_IMAP_PROXY` is unset; managed by the host environment rather than checked-in examples. |

The web deployment uses `packages/web/.env.local.example` as its key-name template. The Mac Mini and Python services use the repository-root `.env.example`. Compare these templates with static code reads before every launch; report key names only.

## Emergency contact and containment

1. The release owner verifies a named primary and backup operator in the access-controlled team roster and the private Feishu operations group before launch. No verified names are stored in this repository; an unresolved primary or backup is a launch blocker.
2. Alert the primary through the private Feishu operations group, include the affected stage, UTC and Asia/Shanghai timestamps, and a non-sensitive run identifier. Escalate to the backup if the roster's response window expires.
3. For a scheduler incident, stop only the exact affected label with `launchctl stop com.aivizens.ai-daily`; do not unload or delete NEV jobs in Phase 0. Preserve the dated and launchd logs.
4. For a web incident, the web production operator uses the Vercel dashboard to identify the current and prior deployments and follows the approved rollback procedure. For email or data incidents, the corresponding owner disables access in the provider dashboard and rotates the affected secret without posting its value.
5. After containment, record the timeline, affected systems, safe evidence, rotation status, and recovery validation in the private incident record. Never attach `.env` files or raw provider responses containing credentials.
