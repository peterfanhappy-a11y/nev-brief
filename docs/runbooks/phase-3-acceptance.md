# Phase 3 acceptance runbook

This gate keeps generation, human approval, publication, and email delivery separate.
The commands below are read-only or no-send unless the operator explicitly enables the
email switch. They must be run against a disposable PostgreSQL database first.

## Shadow run

1. At 06:45, run `generate --date YYYY-MM-DD` with `AI_EMAIL_SEND_ENABLED=false`.
2. Obtain `preview-url --date YYYY-MM-DD`, inspect the signed preview in Codex, and
   verify blockers, warnings, source links, and provider outcomes.
3. Set `AIVIZENS_OPERATOR_ID` and run `approve --date YYYY-MM-DD` only after review.
4. Run `release --date YYYY-MM-DD` with `AI_EMAIL_SEND_ENABLED=false`; publication and
   archive creation may proceed, but Resend must not be called.
5. Record only status/count output from `stats --date YYYY-MM-DD --json`.

The smoke check is read-only and never prints content, recipient addresses, tokens, or
credentials:

```bash
bash ops/smoke/verify-ai-workflow.sh --date YYYY-MM-DD
```

It refuses Supabase production URLs unless `--production-read-only` is supplied.

## Test-recipient acceptance

This is a separate, explicitly authorized operation. Use one controlled address in an
isolated subscriber database and pass `release --only-email ADDRESS`; never use the
production subscriber list for this check. Confirm the confirmation page, one daily
message, source links, rating action, ordinary unsubscribe page, RFC 8058 one-click
unsubscribe, Resend id, and a second release with no duplicate delivery.

## Failure and recovery checks

- blocked or unapproved briefs must return a nonzero/no-op release and create no delivery;
- `AI_EMAIL_SEND_ENABLED=false` must claim no pending rows and call no transport;
- only `transient:*` failed rows below the retry ceiling may be requeued by
  `deliver --retry-transient`;
- sent and permanent failures remain unchanged;
- rerunning release/deliver is idempotent.

## Launch gate status

Automated Task 1–8 evidence is recorded in the SDD ledger. The shadow run and the
controlled test-recipient E2E require the operator's database, test address, and explicit
send authorization; they are not run against production by Codex.
