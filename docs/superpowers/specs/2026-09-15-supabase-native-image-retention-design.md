# Supabase-native Image Retention Design

**Date:** 2026-09-15
**Status:** Approved for implementation planning
**Owner:** Supabase Edge Functions and Supabase Cron

## 1. Decision

MARKA will move scheduled image-retention cleanup from the Render FastAPI service
to a Supabase Edge Function invoked by Supabase Cron. Supabase already owns the
scan metadata and the `raw_images` and `graded_images` buckets, so it should also
own scheduled retention.

The existing retention policy remains unchanged:

- standard-user images become eligible after seven days;
- `DEMO-TEST` images become eligible after fifteen minutes; and
- scan records, scores, marks, ownership, and timestamps are retained.

Render continues to remove each raw upload immediately after a grading attempt.
The Supabase cleanup is the authoritative scheduled reconciler and catches both
expired graded images and any leaked raw images.

## 2. Goals

1. Remove scheduled cleanup's dependency on Render availability and cold starts.
2. Delete files through the supported Supabase Storage API.
3. Preserve all non-image assessment data.
4. Retry transient failures safely on the next scheduled run.
5. Produce useful Cron and Edge Function diagnostics without logging secrets or
   student data.

## 3. Non-goals

- deleting scan database records;
- changing user-triggered image or scan deletion;
- changing immediate raw-image cleanup after grading;
- deleting rows directly from `storage.objects`;
- adding a frontend retention interface;
- adding a new audit table in V1; or
- guaranteeing cleanup while the entire Supabase project is paused.

## 4. Architecture

```text
Supabase Cron (every 15 minutes)
    -> authenticated POST
       /functions/v1/cleanup-expired-images
          -> query eligible rows in public.scans
          -> delete referenced objects through Storage API
          -> clear only successfully handled path columns
          -> return aggregate metrics
```

The Edge Function lives at:

```text
supabase/functions/cleanup-expired-images/
    index.ts       HTTP boundary, authentication, environment, response
    cleanup.ts     retention orchestration against narrow data/storage interfaces
    cleanup.test.ts deterministic unit tests with in-memory fakes
```

A timestamped Supabase migration enables or verifies `pg_cron` and `pg_net`, then
schedules one job named `cleanup-expired-images` with `*/15 * * * *`.

## 5. Retention rules

The function calculates cutoffs in UTC at invocation time:

```text
standard_cutoff = now - 7 days
demo_cutoff     = now - 15 minutes
```

A scan is eligible only when at least one of `image_path` or
`graded_image_path` is non-null and one of these conditions is true:

- its owner is the `DEMO-TEST` user and `created_at < demo_cutoff`; or
- its owner is not the `DEMO-TEST` user and `created_at < standard_cutoff`.

Rows exactly on a cutoff are not eligible until a later run. Cron runs every
fifteen minutes, so a demo image is normally deleted between fifteen and thirty
minutes after creation. Standard images are normally deleted within fifteen
minutes after crossing seven days.

## 6. Deletion and metadata consistency

The fixed bucket-to-column mapping is:

| Bucket | Scan column |
| --- | --- |
| `raw_images` | `image_path` |
| `graded_images` | `graded_image_path` |

The function reads paths only from `public.scans`; request bodies cannot supply
arbitrary bucket names or object paths. Files are deleted with
`supabase.storage.from(bucket).remove(paths)` in bounded batches.

For each successful Storage batch, the corresponding path column is set to null
for those scan IDs. Scores, totals, percentages, raw marks, status, exam links,
user links, and timestamps are not modified. If Storage returns an error, the
function does not clear those paths. They remain eligible and are retried by the
next Cron run.

Deleting an already-missing object is treated as reconciliation success when the
Storage API returns no error; the stale database path is cleared. The operation
is idempotent because later runs select only non-null paths.

## 7. Bounded work

One invocation processes a bounded number of eligible scans, oldest first. The
initial cap is 500 scans per cohort per run, with Storage deletion batches of at
most 100 paths. Remaining eligible rows are handled by later fifteen-minute runs.
This prevents an unexpected backlog from exhausting Edge Function runtime.

The response contains aggregate counts only:

```json
{
  "ok": true,
  "dry_run": false,
  "scans_inspected": 12,
  "raw_paths_cleared": 1,
  "graded_paths_cleared": 11,
  "storage_failures": 0,
  "metadata_failures": 0
}
```

No object paths, user IDs, marks, names, or credentials appear in normal logs or
responses.

## 8. Authentication and secrets

The Edge Function is not an end-user endpoint. Its public URL is protected by a
dedicated high-entropy `CLEANUP_CRON_SECRET` sent in an `X-Cleanup-Secret`
header. The same value is stored in two managed locations:

1. Supabase Edge Function secrets for request validation; and
2. Supabase Vault for the Cron HTTP request.

The project URL is also read by Cron from Vault. Neither value is committed to
Git. The function uses the built-in `SUPABASE_SERVICE_ROLE_KEY` only inside the
Edge runtime. It is never returned, logged, or sent to the browser.

The gateway configuration permits the Cron request through without a user JWT;
the function rejects missing or incorrect cleanup secrets before constructing a
service-role client or querying data.

## 9. Dry run and operational verification

An authenticated request body of `{"dry_run": true}` returns the number of
eligible scans and paths without deleting files or updating rows. Cron always
sends `{"dry_run": false}`. Dry run exists only to validate cutoffs safely during
deployment and incident investigation.

Operations are observed through Supabase Cron history and Edge Function logs.
V1 does not add a cleanup-runs table. Alerts are manual: a maintainer checks the
latest scheduled run after deployment and when storage usage behaves unexpectedly.

## 10. Error handling

- Missing or incorrect secret: return `401`; perform no Supabase operations.
- Missing required environment variables: return `500`; log only the missing
  variable name.
- Demo user absent: treat every scan as standard and report `demo_user_found:
  false`; do not shorten any retention period.
- Candidate-query failure: return `500`; delete nothing.
- Storage batch failure: retain affected database paths, count the failure, and
  continue with independent batches.
- Metadata update failure after Storage success: count and log the row count.
  The next run reconciles the now-missing objects and clears the stale paths.
- Duplicate or overlapping invocations: safe because selection and updates are
  idempotent; no credit or score mutation occurs.

The Cron expression does not overlap under normal load. No distributed lock is
added in V1 because duplicate execution cannot corrupt retained data.

## 11. Testing

Tests drive the implementation through a narrow repository/storage interface and
cover:

1. standard rows before and after seven days;
2. demo rows before and after fifteen minutes;
3. exact cutoff boundaries;
4. raw-only, graded-only, and both-path rows;
5. scan records and score fields remaining unchanged;
6. Storage failure leaving paths available for retry;
7. metadata failure after successful Storage deletion;
8. already-missing objects reconciling successfully;
9. repeat invocation performing no duplicate work;
10. bounded batches and aggregate metrics;
11. dry-run performing no mutations; and
12. missing or invalid secret returning `401` before data access.

Local verification uses Deno tests. Live verification uses one isolated synthetic
scan owned by a controlled test user: upload two tiny objects, backdate only the
test row, run dry mode, run deletion mode, then confirm both objects are absent,
both path columns are null, and score/marks remain intact.

## 12. Deployment sequence

1. Connect tooling to the MARKA Supabase project.
2. Apply the outstanding `scans.layout_mode` migration independently.
3. Create one random cleanup secret in Edge Function secrets and Vault.
4. Deploy `cleanup-expired-images` with its gateway authentication configuration.
5. Invoke dry run and verify eligible counts.
6. Run the controlled live deletion test.
7. Create the fifteen-minute Cron job through the versioned migration.
8. Inspect at least two successful scheduled invocations.
9. Remove the Render `/admin/wipe-expired` scheduled-cleanup implementation and
   its `CRON_SECRET` requirement. Preserve user-triggered `/wipe-image`, scan
   deletion, and immediate raw cleanup.

The Supabase Edge Function becomes the retention owner only after Step 8. Until
then, the Render endpoint remains an emergency fallback.

## 13. Deployment constraint

The currently authenticated Supabase management connector does not expose the
MARKA project reference `tjdzldgccmnspanonthk`. Local service-role credentials can
verify data-plane behavior but cannot deploy Edge Functions or manage Cron. Live
deployment therefore requires connecting the MARKA project to the Supabase CLI or
granting the active Supabase account management access.

## 14. Acceptance criteria

- Supabase Cron invokes the cleanup function every fifteen minutes.
- Unauthorized requests cause no data or Storage access.
- Standard and demo cutoffs match the approved policy.
- Files are removed only through Supabase Storage APIs.
- Failed deletions remain retryable.
- Image paths are cleared only after Storage success or confirmed no-error
  reconciliation.
- Scores, marks, scan rows, and ownership remain unchanged.
- Cron and function output contain no student data or secrets.
- Immediate Render raw cleanup and user-triggered deletion continue to work.
- Render scheduled retention is removed only after two successful Supabase runs.
