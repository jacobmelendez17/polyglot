# Runbook — Backups & Restore (spec §26)

Two things must be backed up independently: the **Postgres database** and the
**object storage** (audio/images). A database backup does **not** protect Storage
files — they need their own mirror.

## Database (Supabase Postgres)

**Beta / MVP** — Supabase automated daily backups (enabled by default on the
project). Retention per plan.

**Paid production** — enable **Point-in-Time Recovery (PITR)** in the Supabase
dashboard (Database → Backups). PITR lets you restore to any second within the
retention window, which is what you want for "someone ran a bad delete at 14:32".

**Manual snapshot before a risky migration**
```bash
pg_dump "$DATABASE_URL" --no-owner --format=custom -f backup-$(date +%F).dump
```

**Restore (staging first — never practise on prod)**
```bash
createdb polyglot_restore
pg_restore --no-owner --clean --if-exists -d polyglot_restore backup-YYYY-MM-DD.dump
# point a staging API at polyglot_restore, run the smoke suite, then cut over
```

Migrations are written to be reversible where possible (`alembic downgrade -1`), but
downgrades are a convenience, **not** a substitute for a real backup — always
snapshot before a destructive migration.

## Object storage (Supabase Storage)

Storage is **not** covered by database backups. Mirror the bucket on a schedule to a
second location (another bucket, S3, or R2). A minimal nightly mirror:

```bash
# requires the supabase CLI (or rclone configured for both ends)
supabase storage cp --recursive "ss:///audio"  "./storage-mirror/audio"
supabase storage cp --recursive "ss:///images" "./storage-mirror/images"
# then sync ./storage-mirror to off-site cold storage (R2/S3) with rclone
rclone sync ./storage-mirror r2:polyglot-backups/$(date +%F)
```

Because audio is content-addressed
(`{content_type}_{content_id}_{locale}_{voice_id}_{version}.{ext}`, §33), the mirror
is append-mostly and cheap to diff.

## Restore test plan (do this quarterly)

1. Spin up a throwaway Postgres and restore the latest dump into it.
2. Restore the storage mirror into a scratch bucket.
3. Run the backend test suite against the restored DB; open the app against the
   scratch bucket and spot-check a lesson with audio.
4. Record the wall-clock restore time (your real RTO) in this file.
5. Tear the scratch resources down.

A backup you have never restored is a hypothesis, not a backup.

## What "reliable" means here (§26)

- In-progress review sessions survive a refresh/disconnect (session state is
  server-side; the queue snapshot is persisted).
- Journal drafts autosave, so accidental navigation doesn't lose typed text.
- Failed submissions retry safely via idempotency keys (reviews/practice), so a
  retried request never double-counts.
- Destructive admin actions soft-delete (archive) first; permanent deletion is a
  separate, owner-gated step from the archive.
