# Supabase Image Retention Runbook

## Ownership and policy

Supabase owns MARKA's scheduled image cleanup. Render still deletes a raw upload
immediately after each grading attempt, and authenticated teachers can still use
the manual image-deletion endpoints.

| Cohort | Eligibility rule | Expected deletion window |
| --- | --- | --- |
| Standard | `created_at < now() - 7 days` | Within 15 minutes after seven days |
| `DEMO-TEST` | `created_at < now() - 15 minutes` | Between 15 and 30 minutes |

Cleanup deletes objects from `raw_images` and `graded_images`, then clears only
the matching `image_path` or `graded_image_path`. It never deletes scan rows,
scores, totals, percentages, raw marks, ownership, status, or timestamps.

## Local verification

From the repository root:

```bash
/home/dafe/.deno/bin/deno fmt --check \
  supabase/functions/cleanup-expired-images
/home/dafe/.deno/bin/deno lint \
  supabase/functions/cleanup-expired-images
/home/dafe/.deno/bin/deno test \
  supabase/functions/cleanup-expired-images
/home/dafe/.deno/bin/deno check \
  supabase/functions/cleanup-expired-images/index.ts
.venv/bin/python -m pytest -q tests/test_supabase_retention_config.py
```

All checks must pass before a deployment.

## Deployment prerequisites

- The active Supabase CLI account must list project
  `tjdzldgccmnspanonthk`.
- `migrations/002_add_scan_layout_mode.sql` must be applied and
  `public.scans.layout_mode` must exist.
- Buckets `raw_images` and `graded_images` must exist.
- No Cron job is enabled until dry-run and isolated live verification pass.
- The Render fallback remains deployed until two scheduled runs succeed.

Confirm the CLI and link:

```bash
npx supabase --version
npx supabase projects list
npx supabase link --project-ref tjdzldgccmnspanonthk
```

Stop if the listed or linked project reference differs.

## Secret provisioning

Generate one 64-character secret in a permission-restricted temporary file:

```bash
RETENTION_SECRET_FILE="$(mktemp)"
export RETENTION_SECRET_FILE
chmod 600 "$RETENTION_SECRET_FILE"
openssl rand -hex 32 > "$RETENTION_SECRET_FILE"
```

Set the Edge Function secret without printing it:

```bash
RETENTION_ENV_FILE="$(mktemp)"
chmod 600 "$RETENTION_ENV_FILE"
printf 'CLEANUP_CRON_SECRET=%s\n' \
  "$(<"$RETENTION_SECRET_FILE")" > "$RETENTION_ENV_FILE"
npx supabase secrets set \
  --project-ref tjdzldgccmnspanonthk \
  --env-file "$RETENTION_ENV_FILE"
shred -u "$RETENTION_ENV_FILE"
```

Create uniquely named Vault entries. The command substitution reads the secret
from the temporary file without placing its value in this repository:

```bash
npx supabase db query --linked --sql \
  "select vault.create_secret(
    'https://tjdzldgccmnspanonthk.supabase.co',
    'project_url',
    'MARKA Edge Function base URL'
  );"
npx supabase db query --linked --sql \
  "select vault.create_secret(
    '$(<"$RETENTION_SECRET_FILE")',
    'cleanup_cron_secret',
    'Authenticates the image-retention Cron request'
  );"
```

Do not copy either expanded command into a ticket or deployment log. Verify names
without selecting decrypted values:

```sql
select name, description, created_at, updated_at
from vault.secrets
where name in ('project_url', 'cleanup_cron_secret')
order by name;
```

## Function deployment and dry run

Deploy before applying the Cron migration:

```bash
npx supabase functions deploy cleanup-expired-images \
  --project-ref tjdzldgccmnspanonthk \
  --no-verify-jwt \
  --use-api
```

An incorrect secret must return 401:

```bash
curl --silent --output /dev/null --write-out "%{http_code}\n" \
  -X POST \
  -H "Content-Type: application/json" \
  -H "X-Cleanup-Secret: incorrect" \
  -d '{"dry_run":true}' \
  https://tjdzldgccmnspanonthk.supabase.co/functions/v1/cleanup-expired-images
```

Expected: `401`.

Invoke an authenticated dry run:

```bash
curl --fail-with-body --silent --show-error \
  -X POST \
  -H "Content-Type: application/json" \
  -H "X-Cleanup-Secret: $(<"$RETENTION_SECRET_FILE")" \
  -d '{"dry_run":true}' \
  https://tjdzldgccmnspanonthk.supabase.co/functions/v1/cleanup-expired-images
```

Expected: HTTP 200, `"ok": true`, `"dry_run": true`, and aggregate counts
only. Paths, IDs, marks, and credentials must not appear.

## Controlled live verification

Before enabling Cron:

1. Create a uniquely named, disabled non-demo test user.
2. Upload one tiny unique object to each managed bucket.
3. Insert one scan for that user with both paths, non-zero score fields, and a
   timestamp older than seven days.
4. Dry-run and prove both objects and both path columns remain.
5. Invoke `{"dry_run": false}`.
6. Prove both objects are absent and both path columns are null.
7. Prove the scan row, owner, score, total, percentage, raw marks, status,
   layout mode, and timestamps are unchanged.
8. Delete only the synthetic scan and user.

If any assertion fails, do not schedule the function. Inspect Edge logs while
the Render fallback remains available.

## Enable and observe Cron

Apply only after controlled live verification passes:

```bash
npx supabase db query --linked \
  --file supabase/migrations/20260915105434_schedule_image_retention.sql
```

MARKA has historical remote migration versions that predate this repository's
`supabase/migrations` directory. For that reason, `supabase db push --linked`
refuses with `LegacyDbPushMissingLocalError`. Do not mark those historical
versions reverted. Apply this reviewed file directly as shown above, then verify
the job. A future migration-baseline project can reconcile the full history
separately.

Confirm exactly one active job:

```sql
select jobid, jobname, schedule, active
from cron.job
where jobname = 'cleanup-expired-images';
```

Inspect history:

```sql
select
  jobid,
  runid,
  status,
  return_message,
  start_time,
  end_time
from cron.job_run_details
where jobid = (
  select jobid
  from cron.job
  where jobname = 'cleanup-expired-images'
)
order by start_time desc
limit 10;
```

Wait through at least two fifteen-minute boundaries. Remove the Render scheduled
endpoint and `CRON_SECRET` only after the latest two runs succeed and their Edge
responses contain aggregate data only.

## Failure handling

- `401`: confirm the Vault and Edge values match, then rotate if uncertain.
- `500` before data access: check that the Edge environment exposes
  `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`.
- Storage failure count above zero: leave paths intact and let the next run retry.
- Metadata failure count above zero: the next run treats already-missing objects
  as reconciled and retries clearing their paths.
- Demo user absent: all scans remain on the safer seven-day policy.
- Candidate-query failure: nothing is deleted.

Never delete directly from `storage.objects`.

## Rollback

Stop future schedules:

```sql
select cron.unschedule(jobid)
from cron.job
where jobname = 'cleanup-expired-images';
```

If Render scheduled cleanup has already been removed, redeploy the last known
good Render revision only when scheduled retention is still required during the
incident. Rollback does not restore already-deleted image objects. Scan records
and assessment results remain available.

## Secret rotation

1. Generate a new secret file as described above.
2. Find the Vault secret UUID without selecting its decrypted value:

   ```sql
   select id, name
   from vault.secrets
   where name = 'cleanup_cron_secret';
   ```

3. Update the Vault value with `vault.update_secret(secret_uuid, new_value)`.
4. Set the same new value as the Edge `CLEANUP_CRON_SECRET`.
5. Invoke one authenticated dry run with the new value.
6. Securely remove the temporary file:

   ```bash
   shred -u "$RETENTION_SECRET_FILE"
   unset RETENTION_SECRET_FILE
   ```

Do not record the cleanup secret, service-role key, object paths, user IDs,
marks, or student data in tickets or deployment notes.
