# Supabase-native Image Retention Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move MARKA's scheduled raw and graded image retention from Render to an authenticated Supabase Edge Function invoked every fifteen minutes by Supabase Cron, without deleting scan results.

**Architecture:** A pure Deno cleanup module owns cutoff calculation, bounded batching, and per-bucket consistency. A thin Supabase adapter queries `public.scans`, deletes through the Storage API, and nulls only successfully reconciled path columns. A versioned migration schedules the authenticated HTTP invocation; Render's scheduled endpoint remains until two successful Cron runs prove the new owner.

**Tech Stack:** Deno 2, TypeScript, `@supabase/supabase-js`, Supabase Edge Functions, PostgreSQL `pg_cron`/`pg_net`/Vault, Python `pytest`, FastAPI, Render Blueprint

---

## File map

- Create `supabase/config.toml` — local Supabase configuration and Edge gateway setting.
- Create `supabase/functions/cleanup-expired-images/cleanup.ts` — pure retention policy and orchestration.
- Create `supabase/functions/cleanup-expired-images/cleanup.test.ts` — deterministic policy, batching, failure, and authentication tests.
- Create `supabase/functions/cleanup-expired-images/index.ts` — Supabase database/Storage adapter and Edge entry point.
- Create `supabase/functions/cleanup-expired-images/index.test.ts` — adapter query and path-update contract tests.
- Create `supabase/migrations/20260915105434_schedule_image_retention.sql` — extensions and fifteen-minute Cron job.
- Create `tests/test_supabase_retention_config.py` — static deployment-safety assertions for function config and migration.
- Create `docs/supabase_image_retention_runbook.md` — deployment, observation, rollback, and secret-rotation procedure.
- Modify `README.md` — document the retention owner and local verification commands.
- Modify `api/test_server.py` — protect the cutover by first asserting the old scheduled route is absent.
- Modify `api/server.py:907-963` — remove only the old scheduled cleanup function and admin route after live proof.
- Modify `render.yaml:30-32` — remove only the obsolete `CRON_SECRET` declaration after live proof.

## Non-negotiable invariants

- Standard images use a strict seven-day cutoff; `DEMO-TEST` images use a strict fifteen-minute cutoff.
- Scan rows, scores, marks, ownership, timestamps, and status are retained.
- `raw_images` maps only to `image_path`; `graded_images` maps only to `graded_image_path`.
- A failed Storage batch leaves its database paths non-null for retry.
- An authenticated dry run performs no Storage or database mutation.
- No request body may provide a bucket, object path, cutoff, or user ID.
- Responses and logs contain aggregate counts only.
- Render's immediate post-grading raw cleanup and user-triggered deletion routes remain.

### Task 1: Initialize the Supabase workspace and define the HTTP boundary

**Files:**
- Create: `supabase/config.toml`
- Create: `supabase/functions/cleanup-expired-images/cleanup.ts`
- Test: `supabase/functions/cleanup-expired-images/cleanup.test.ts`

- [ ] **Step 1: Initialize the local Supabase directory**

Run:

```bash
npx supabase init --yes
```

Expected: `supabase/config.toml` is created. Do not add a project reference or credential to it.

- [ ] **Step 2: Write the failing policy and authorization tests**

Create `supabase/functions/cleanup-expired-images/cleanup.test.ts`:

```ts
import {
  createCleanupHandler,
  retentionCutoffs,
  type CleanupReport,
} from "./cleanup.ts";

Deno.test("retentionCutoffs uses seven days and fifteen minutes", () => {
  const now = new Date("2026-09-15T12:00:00.000Z");
  const cutoffs = retentionCutoffs(now);
  if (cutoffs.standard !== "2026-09-08T12:00:00.000Z") {
    throw new Error(cutoffs.standard);
  }
  if (cutoffs.demo !== "2026-09-15T11:45:00.000Z") {
    throw new Error(cutoffs.demo);
  }
});

Deno.test("missing function secret returns 500 before cleanup", async () => {
  let calls = 0;
  const handler = createCleanupHandler({
    secret: "",
    cleanup: async () => {
      calls += 1;
      return {} as CleanupReport;
    },
  });
  const response = await handler(new Request("http://local", { method: "POST" }));
  if (response.status !== 500 || calls !== 0) throw new Error("unsafe request");
});

Deno.test("incorrect secret returns 401 before cleanup", async () => {
  let calls = 0;
  const handler = createCleanupHandler({
    secret: "correct",
    cleanup: async () => {
      calls += 1;
      return {} as CleanupReport;
    },
  });
  const response = await handler(new Request("http://local", {
    method: "POST",
    headers: { "X-Cleanup-Secret": "wrong" },
  }));
  if (response.status !== 401 || calls !== 0) throw new Error("unsafe request");
});

Deno.test("authenticated dry run reaches cleanup once", async () => {
  let dryRun: boolean | undefined;
  const report = {
    ok: true,
    dry_run: true,
    demo_user_found: true,
    scans_inspected: 0,
    raw_paths_eligible: 0,
    graded_paths_eligible: 0,
    raw_paths_cleared: 0,
    graded_paths_cleared: 0,
    storage_failures: 0,
    metadata_failures: 0,
  };
  const handler = createCleanupHandler({
    secret: "correct",
    cleanup: async (value) => {
      dryRun = value;
      return report;
    },
  });
  const response = await handler(new Request("http://local", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Cleanup-Secret": "correct",
    },
    body: JSON.stringify({ dry_run: true }),
  }));
  if (response.status !== 200 || dryRun !== true) throw new Error("bad request");
});
```

- [ ] **Step 3: Run the tests to prove the module is missing**

Run:

```bash
deno test supabase/functions/cleanup-expired-images/cleanup.test.ts
```

Expected: FAIL because `./cleanup.ts` does not exist.

- [ ] **Step 4: Add the minimal policy types and authenticated handler**

Create `supabase/functions/cleanup-expired-images/cleanup.ts`:

```ts
export const SCAN_LIMIT = 500;
export const STORAGE_BATCH_SIZE = 100;

export type Cohort = "demo" | "standard";
export type PathColumn = "image_path" | "graded_image_path";
export type Bucket = "raw_images" | "graded_images";

export interface ScanRow {
  id: string;
  user_id: string;
  image_path: string | null;
  graded_image_path: string | null;
  created_at: string;
}

export interface CleanupStore {
  findDemoUserId(): Promise<string | null>;
  listCandidates(args: {
    cohort: Cohort;
    cutoff: string;
    demoUserId: string | null;
    limit: number;
  }): Promise<ScanRow[]>;
  removeObjects(bucket: Bucket, paths: string[]): Promise<void>;
  clearPaths(column: PathColumn, ids: string[]): Promise<void>;
}

export interface CleanupReport {
  ok: boolean;
  dry_run: boolean;
  demo_user_found: boolean;
  scans_inspected: number;
  raw_paths_eligible: number;
  graded_paths_eligible: number;
  raw_paths_cleared: number;
  graded_paths_cleared: number;
  storage_failures: number;
  metadata_failures: number;
}

export function retentionCutoffs(now: Date) {
  return {
    standard: new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString(),
    demo: new Date(now.getTime() - 15 * 60 * 1000).toISOString(),
  };
}

function json(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function createCleanupHandler(deps: {
  secret: string;
  cleanup: (dryRun: boolean) => Promise<CleanupReport>;
}) {
  return async (request: Request): Promise<Response> => {
    if (request.method !== "POST") return json({ error: "Method not allowed" }, 405);
    if (!deps.secret) return json({ error: "Configuration error" }, 500);
    if (request.headers.get("X-Cleanup-Secret") !== deps.secret) {
      return json({ error: "Unauthorized" }, 401);
    }

    let payload: unknown = {};
    try {
      const text = await request.text();
      payload = text ? JSON.parse(text) : {};
    } catch {
      return json({ error: "Invalid JSON" }, 400);
    }
    const dryRun = typeof payload === "object" && payload !== null &&
      (payload as { dry_run?: unknown }).dry_run === true;
    try {
      return json(await deps.cleanup(dryRun), 200);
    } catch {
      return json({ error: "Cleanup failed" }, 500);
    }
  };
}
```

- [ ] **Step 5: Run formatting and tests**

Run:

```bash
deno fmt supabase/functions/cleanup-expired-images
deno test supabase/functions/cleanup-expired-images/cleanup.test.ts
```

Expected: all four tests PASS.

- [ ] **Step 6: Commit the boundary**

```bash
git add supabase/config.toml supabase/functions/cleanup-expired-images
git commit -m "feat: define Supabase image retention boundary"
```

### Task 2: Implement bounded, retry-safe cleanup orchestration

**Files:**
- Modify: `supabase/functions/cleanup-expired-images/cleanup.ts`
- Test: `supabase/functions/cleanup-expired-images/cleanup.test.ts`

- [ ] **Step 1: Add a deterministic fake store and failing cleanup tests**

Append to `cleanup.test.ts`:

```ts
import {
  runCleanup,
  type Bucket,
  type CleanupStore,
  type PathColumn,
  type ScanRow,
} from "./cleanup.ts";

class FakeStore implements CleanupStore {
  demoUserId: string | null = "demo-user";
  rows: Record<"demo" | "standard", ScanRow[]> = { demo: [], standard: [] };
  candidateCalls: Array<{
    cohort: "demo" | "standard";
    cutoff: string;
    demoUserId: string | null;
    limit: number;
  }> = [];
  removed: Array<{ bucket: Bucket; paths: string[] }> = [];
  cleared: Array<{ column: PathColumn; ids: string[] }> = [];
  failingBucket: Bucket | null = null;
  failMetadata = false;

  async findDemoUserId() {
    return this.demoUserId;
  }
  async listCandidates(args: {
    cohort: "demo" | "standard";
    cutoff: string;
    demoUserId: string | null;
    limit: number;
  }) {
    this.candidateCalls.push(args);
    return this.rows[args.cohort];
  }
  async removeObjects(bucket: Bucket, paths: string[]) {
    if (this.failingBucket === bucket) throw new Error("storage");
    this.removed.push({ bucket, paths });
  }
  async clearPaths(column: PathColumn, ids: string[]) {
    if (this.failMetadata) throw new Error("metadata");
    this.cleared.push({ column, ids });
  }
}

function row(id: string, raw: string | null, graded: string | null): ScanRow {
  return {
    id,
    user_id: "standard-user",
    image_path: raw,
    graded_image_path: graded,
    created_at: "2026-09-01T00:00:00.000Z",
  };
}

Deno.test("cleanup removes both layers and clears only their path columns", async () => {
  const store = new FakeStore();
  store.rows.standard = [row("one", "raw/one.jpg", "graded/one.jpg")];
  const report = await runCleanup(store, false, new Date("2026-09-15T12:00:00Z"));

  if (report.scans_inspected !== 1) throw new Error("wrong scan count");
  if (report.raw_paths_cleared !== 1 || report.graded_paths_cleared !== 1) {
    throw new Error("wrong clear count");
  }
  if (store.removed.length !== 2 || store.cleared.length !== 2) {
    throw new Error("missing mutation");
  }
  if (store.cleared[0].column === store.cleared[1].column) {
    throw new Error("columns were not isolated");
  }
});

Deno.test("dry run counts paths without mutating storage or rows", async () => {
  const store = new FakeStore();
  store.rows.demo = [row("demo", "raw/demo.jpg", null)];
  const report = await runCleanup(store, true, new Date("2026-09-15T12:00:00Z"));

  if (!report.dry_run || report.raw_paths_eligible !== 1) throw new Error("bad report");
  if (store.removed.length || store.cleared.length) throw new Error("dry run mutated");
});

Deno.test("storage failure leaves the matching paths available for retry", async () => {
  const store = new FakeStore();
  store.rows.standard = [row("one", "raw/one.jpg", "graded/one.jpg")];
  store.failingBucket = "raw_images";
  const report = await runCleanup(store, false, new Date("2026-09-15T12:00:00Z"));

  if (report.raw_paths_cleared !== 0 || report.storage_failures !== 1) {
    throw new Error("raw failure was hidden");
  }
  if (report.graded_paths_cleared !== 1) throw new Error("independent batch stopped");
  if (store.cleared.some((call) => call.column === "image_path")) {
    throw new Error("failed raw metadata was cleared");
  }
});

Deno.test("metadata failure is reported after successful Storage deletion", async () => {
  const store = new FakeStore();
  store.rows.standard = [row("one", "raw/one.jpg", null)];
  store.failMetadata = true;
  const report = await runCleanup(store, false, new Date("2026-09-15T12:00:00Z"));

  if (store.removed.length !== 1 || report.metadata_failures !== 1 || report.ok) {
    throw new Error("metadata failure was hidden");
  }
});
```

- [ ] **Step 2: Run the tests to verify the new import fails**

Run:

```bash
deno test supabase/functions/cleanup-expired-images/cleanup.test.ts
```

Expected: FAIL because `runCleanup` is not exported.

- [ ] **Step 3: Implement cleanup and batch processing**

Append to `cleanup.ts`:

```ts
function chunks<T>(items: T[], size: number): T[][] {
  const result: T[][] = [];
  for (let index = 0; index < items.length; index += size) {
    result.push(items.slice(index, index + size));
  }
  return result;
}

export async function runCleanup(
  store: CleanupStore,
  dryRun: boolean,
  now = new Date(),
): Promise<CleanupReport> {
  const cutoffs = retentionCutoffs(now);
  const demoUserId = await store.findDemoUserId();
  const [demoRows, standardRows] = await Promise.all([
    demoUserId
      ? store.listCandidates({
        cohort: "demo",
        cutoff: cutoffs.demo,
        demoUserId,
        limit: SCAN_LIMIT,
      })
      : Promise.resolve([]),
    store.listCandidates({
      cohort: "standard",
      cutoff: cutoffs.standard,
      demoUserId,
      limit: SCAN_LIMIT,
    }),
  ]);

  const scans = [...new Map(
    [...demoRows, ...standardRows].map((scan) => [scan.id, scan]),
  ).values()];
  const raw = scans
    .filter((scan) => scan.image_path !== null)
    .map((scan) => ({ id: scan.id, path: scan.image_path as string }));
  const graded = scans
    .filter((scan) => scan.graded_image_path !== null)
    .map((scan) => ({ id: scan.id, path: scan.graded_image_path as string }));

  const report: CleanupReport = {
    ok: true,
    dry_run: dryRun,
    demo_user_found: demoUserId !== null,
    scans_inspected: scans.length,
    raw_paths_eligible: raw.length,
    graded_paths_eligible: graded.length,
    raw_paths_cleared: 0,
    graded_paths_cleared: 0,
    storage_failures: 0,
    metadata_failures: 0,
  };
  if (dryRun) return report;

  async function process(
    bucket: Bucket,
    column: PathColumn,
    objects: Array<{ id: string; path: string }>,
    clearedKey: "raw_paths_cleared" | "graded_paths_cleared",
  ) {
    for (const batch of chunks(objects, STORAGE_BATCH_SIZE)) {
      try {
        await store.removeObjects(bucket, batch.map((item) => item.path));
      } catch {
        report.storage_failures += batch.length;
        continue;
      }
      try {
        await store.clearPaths(column, batch.map((item) => item.id));
        report[clearedKey] += batch.length;
      } catch {
        report.metadata_failures += batch.length;
      }
    }
  }

  await process("raw_images", "image_path", raw, "raw_paths_cleared");
  await process(
    "graded_images",
    "graded_image_path",
    graded,
    "graded_paths_cleared",
  );
  report.ok = report.storage_failures === 0 && report.metadata_failures === 0;
  return report;
}
```

- [ ] **Step 4: Add boundary, repeat-run, and batch-size assertions**

Append to `cleanup.test.ts`:

```ts
Deno.test("cleanup sends exact UTC cutoffs and deduplicates cohort results", async () => {
  const store = new FakeStore();
  const duplicate = row("same", "raw/same.jpg", null);
  store.rows.demo = [duplicate];
  store.rows.standard = [duplicate];

  const report = await runCleanup(
    store,
    true,
    new Date("2026-09-15T12:00:00.000Z"),
  );
  const demoCall = store.candidateCalls.find((call) => call.cohort === "demo");
  const standardCall = store.candidateCalls.find(
    (call) => call.cohort === "standard",
  );
  if (demoCall?.cutoff !== "2026-09-15T11:45:00.000Z") {
    throw new Error("wrong demo cutoff");
  }
  if (standardCall?.cutoff !== "2026-09-08T12:00:00.000Z") {
    throw new Error("wrong standard cutoff");
  }
  if (demoCall.limit !== 500 || standardCall.limit !== 500) {
    throw new Error("unbounded query");
  }
  if (report.scans_inspected !== 1 || report.raw_paths_eligible !== 1) {
    throw new Error("duplicate scan counted");
  }
});

Deno.test("cleanup splits Storage work into batches of at most 100", async () => {
  const store = new FakeStore();
  store.rows.standard = Array.from(
    { length: 101 },
    (_, index) => row(String(index), `raw/${index}.jpg`, null),
  );

  const report = await runCleanup(
    store,
    false,
    new Date("2026-09-15T12:00:00.000Z"),
  );
  const sizes = store.removed
    .filter((call) => call.bucket === "raw_images")
    .map((call) => call.paths.length);
  if (JSON.stringify(sizes) !== JSON.stringify([100, 1])) {
    throw new Error(`wrong batches: ${JSON.stringify(sizes)}`);
  }
  if (report.raw_paths_cleared !== 101) throw new Error("wrong clear count");
});

Deno.test("repeat invocation with no candidates performs no duplicate work", async () => {
  const store = new FakeStore();
  store.rows.standard = [row("one", "raw/one.jpg", null)];
  await runCleanup(store, false, new Date("2026-09-15T12:00:00.000Z"));
  const firstRemovalCount = store.removed.length;
  const firstClearCount = store.cleared.length;

  store.rows.standard = [];
  const report = await runCleanup(
    store,
    false,
    new Date("2026-09-15T12:15:00.000Z"),
  );
  if (report.scans_inspected !== 0) throw new Error("stale candidate repeated");
  if (
    store.removed.length !== firstRemovalCount ||
    store.cleared.length !== firstClearCount
  ) {
    throw new Error("duplicate mutation");
  }
});
```

- [ ] **Step 5: Run all Deno quality checks**

Run:

```bash
deno fmt supabase/functions/cleanup-expired-images
deno lint supabase/functions/cleanup-expired-images
deno test supabase/functions/cleanup-expired-images
```

Expected: formatting succeeds, lint reports no errors, and every test passes.

- [ ] **Step 6: Commit the engine**

```bash
git add supabase/functions/cleanup-expired-images
git commit -m "feat: add retry-safe image retention engine"
```

### Task 3: Implement and test the Supabase adapter

**Files:**
- Create: `supabase/functions/cleanup-expired-images/index.ts`
- Create: `supabase/functions/cleanup-expired-images/index.test.ts`

- [ ] **Step 1: Write a failing adapter contract test**

Create `supabase/functions/cleanup-expired-images/index.test.ts`:

```ts
import type { SupabaseClient } from "npm:@supabase/supabase-js@2.116.0";
import { SupabaseCleanupStore } from "./index.ts";

type Call = unknown[];
type Result = { data: unknown; error: Error | null };

function assertCall(calls: Call[], expected: Call) {
  const wanted = JSON.stringify(expected);
  if (!calls.some((call) => JSON.stringify(call) === wanted)) {
    throw new Error(`missing call ${wanted}: ${JSON.stringify(calls)}`);
  }
}

function fakeSupabase(result: Result) {
  const calls: Call[] = [];
  const query: Record<string, (...args: unknown[]) => unknown> = {};
  for (
    const method of [
      "select",
      "eq",
      "neq",
      "lt",
      "or",
      "order",
      "update",
    ]
  ) {
    query[method] = (...args: unknown[]) => {
      calls.push([method, ...args]);
      return query;
    };
  }
  for (const method of ["limit", "in"]) {
    query[method] = (...args: unknown[]) => {
      calls.push([method, ...args]);
      return Promise.resolve(result);
    };
  }
  query.maybeSingle = () => {
    calls.push(["maybeSingle"]);
    return Promise.resolve(result);
  };

  const client = {
    from: (table: string) => {
      calls.push(["from", table]);
      return query;
    },
    storage: {
      from: (bucket: string) => {
        calls.push(["storage.from", bucket]);
        return {
          remove: (paths: string[]) => {
            calls.push(["remove", paths]);
            return Promise.resolve(result);
          },
        };
      },
    },
  } as unknown as SupabaseClient;
  return { client, calls };
}

Deno.test("demo query is old-first, bounded, strict, and scoped to demo", async () => {
  const { client, calls } = fakeSupabase({ data: [], error: null });
  const store = new SupabaseCleanupStore(client);
  await store.listCandidates({
    cohort: "demo",
    cutoff: "2026-09-15T11:45:00.000Z",
    demoUserId: "demo-id",
    limit: 500,
  });
  assertCall(calls, ["lt", "created_at", "2026-09-15T11:45:00.000Z"]);
  assertCall(calls, ["eq", "user_id", "demo-id"]);
  assertCall(calls, ["or", "image_path.not.is.null,graded_image_path.not.is.null"]);
  assertCall(calls, ["order", "created_at", { ascending: true }]);
  assertCall(calls, ["limit", 500]);
});

Deno.test("standard query excludes demo when the demo account exists", async () => {
  const { client, calls } = fakeSupabase({ data: [], error: null });
  const store = new SupabaseCleanupStore(client);
  await store.listCandidates({
    cohort: "standard",
    cutoff: "2026-09-08T12:00:00.000Z",
    demoUserId: "demo-id",
    limit: 500,
  });
  assertCall(calls, ["neq", "user_id", "demo-id"]);
});

Deno.test("path clearing updates only the requested column", async () => {
  const { client, calls } = fakeSupabase({ data: [], error: null });
  const store = new SupabaseCleanupStore(client);
  await store.clearPaths("image_path", ["scan-one"]);
  assertCall(calls, ["update", { image_path: null }]);
  assertCall(calls, ["in", "id", ["scan-one"]]);
});

Deno.test("Storage deletion stays inside the selected fixed bucket", async () => {
  const { client, calls } = fakeSupabase({ data: [], error: null });
  const store = new SupabaseCleanupStore(client);
  await store.removeObjects("graded_images", ["graded/scan-one.jpg"]);
  assertCall(calls, ["storage.from", "graded_images"]);
  assertCall(calls, ["remove", ["graded/scan-one.jpg"]]);
});
```

- [ ] **Step 2: Run the adapter test to verify it fails**

Run:

```bash
deno test supabase/functions/cleanup-expired-images/index.test.ts
```

Expected: FAIL because `index.ts` does not exist.

- [ ] **Step 3: Implement the adapter and Edge entry point**

Create `supabase/functions/cleanup-expired-images/index.ts`:

```ts
import {
  createClient,
  type SupabaseClient,
} from "npm:@supabase/supabase-js@2.116.0";
import {
  createCleanupHandler,
  type Bucket,
  type CleanupStore,
  type Cohort,
  type PathColumn,
  runCleanup,
  type ScanRow,
} from "./cleanup.ts";

export class SupabaseCleanupStore implements CleanupStore {
  constructor(private readonly client: SupabaseClient) {}

  async findDemoUserId(): Promise<string | null> {
    const { data, error } = await this.client
      .from("users")
      .select("id")
      .eq("marka_id", "DEMO-TEST")
      .maybeSingle();
    if (error) throw error;
    return data?.id ?? null;
  }

  async listCandidates(args: {
    cohort: Cohort;
    cutoff: string;
    demoUserId: string | null;
    limit: number;
  }): Promise<ScanRow[]> {
    let query = this.client
      .from("scans")
      .select("id,user_id,image_path,graded_image_path,created_at")
      .lt("created_at", args.cutoff)
      .or("image_path.not.is.null,graded_image_path.not.is.null");

    if (args.cohort === "demo") {
      if (!args.demoUserId) return [];
      query = query.eq("user_id", args.demoUserId);
    } else if (args.demoUserId) {
      query = query.neq("user_id", args.demoUserId);
    }

    const { data, error } = await query
      .order("created_at", { ascending: true })
      .limit(args.limit);
    if (error) throw error;
    return (data ?? []) as ScanRow[];
  }

  async removeObjects(bucket: Bucket, paths: string[]): Promise<void> {
    const { error } = await this.client.storage.from(bucket).remove(paths);
    if (error) throw error;
  }

  async clearPaths(column: PathColumn, ids: string[]): Promise<void> {
    const { error } = await this.client
      .from("scans")
      .update({ [column]: null })
      .in("id", ids);
    if (error) throw error;
  }
}

export function buildHandler(env = Deno.env) {
  const secret = env.get("CLEANUP_CRON_SECRET") ?? "";
  return createCleanupHandler({
    secret,
    cleanup: async (dryRun) => {
      const url = env.get("SUPABASE_URL");
      const serviceRoleKey = env.get("SUPABASE_SERVICE_ROLE_KEY");
      if (!url) {
        console.error("Missing required environment variable: SUPABASE_URL");
        throw new Error("configuration");
      }
      if (!serviceRoleKey) {
        console.error(
          "Missing required environment variable: SUPABASE_SERVICE_ROLE_KEY",
        );
        throw new Error("configuration");
      }
      const store = new SupabaseCleanupStore(createClient(url, serviceRoleKey));
      return await runCleanup(store, dryRun);
    },
  });
}

if (import.meta.main) Deno.serve(buildHandler());
```

- [ ] **Step 4: Verify imports, adapter tests, and the whole function**

Run:

```bash
deno fmt supabase/functions/cleanup-expired-images
deno lint supabase/functions/cleanup-expired-images
deno test supabase/functions/cleanup-expired-images
deno check supabase/functions/cleanup-expired-images/index.ts
```

Expected: all commands exit zero. The first run may download the pinned npm package.

- [ ] **Step 5: Commit the adapter**

```bash
git add supabase/functions/cleanup-expired-images
git commit -m "feat: connect image retention to Supabase"
```

### Task 4: Add the gateway configuration and Cron migration

**Files:**
- Modify: `supabase/config.toml`
- Create: `supabase/migrations/20260915105434_schedule_image_retention.sql`
- Create: `tests/test_supabase_retention_config.py`

- [ ] **Step 1: Write the failing static deployment-safety tests**

Create `tests/test_supabase_retention_config.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _migration_text() -> str:
    matches = list(
        (ROOT / "supabase" / "migrations").glob(
            "*_schedule_image_retention.sql"
        )
    )
    assert len(matches) == 1
    return matches[0].read_text()


def test_edge_gateway_uses_function_level_secret():
    config = (ROOT / "supabase" / "config.toml").read_text()
    assert "[functions.cleanup-expired-images]" in config
    assert "verify_jwt = false" in config
    assert "tjdzldgccmnspanonthk" not in config
    assert "service_role" not in config.lower()


def test_cron_is_bounded_to_the_fixed_function_and_secret_header():
    sql = _migration_text()
    assert "create extension if not exists pg_cron" in sql.lower()
    assert "create extension if not exists pg_net" in sql.lower()
    assert "'cleanup-expired-images'" in sql
    assert "'*/15 * * * *'" in sql
    assert "/functions/v1/cleanup-expired-images" in sql
    assert "'X-Cleanup-Secret'" in sql
    assert "cleanup_cron_secret" in sql
    assert "project_url" in sql
    assert "jsonb_build_object('dry_run', false)" in sql
    assert "service_role" not in sql.lower()
```

- [ ] **Step 2: Run the tests to verify configuration is absent**

Run:

```bash
pytest -q tests/test_supabase_retention_config.py
```

Expected: FAIL because the function block and schedule migration are absent.

- [ ] **Step 3: Add function-level gateway configuration**

Append to `supabase/config.toml`:

```toml
[functions.cleanup-expired-images]
verify_jwt = false
```

This allows the Cron call through the gateway; `X-Cleanup-Secret` remains mandatory inside the function.

- [ ] **Step 4: Create the Cron migration**

Create `supabase/migrations/20260915105434_schedule_image_retention.sql`:

```sql
create extension if not exists pg_cron;
create extension if not exists pg_net with schema extensions;

select cron.unschedule(jobid)
from cron.job
where jobname = 'cleanup-expired-images';

select cron.schedule(
  'cleanup-expired-images',
  '*/15 * * * *',
  $job$
  select net.http_post(
    url := rtrim(
      (
        select decrypted_secret
        from vault.decrypted_secrets
        where name = 'project_url'
      ),
      '/'
    ) || '/functions/v1/cleanup-expired-images',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'X-Cleanup-Secret',
      (
        select decrypted_secret
        from vault.decrypted_secrets
        where name = 'cleanup_cron_secret'
      )
    ),
    body := jsonb_build_object('dry_run', false),
    timeout_milliseconds := 60000
  );
  $job$
);
```

The unschedule query makes re-application converge on one named job.

- [ ] **Step 5: Run static and Deno checks**

Run:

```bash
pytest -q tests/test_supabase_retention_config.py
deno test supabase/functions/cleanup-expired-images
deno check supabase/functions/cleanup-expired-images/index.ts
```

Expected: every command passes.

- [ ] **Step 6: Commit configuration and migration**

```bash
git add supabase/config.toml supabase/migrations tests/test_supabase_retention_config.py
git commit -m "feat: schedule Supabase image retention"
```

### Task 5: Document operation and rollback

**Files:**
- Create: `docs/supabase_image_retention_runbook.md`
- Modify: `README.md`

- [ ] **Step 1: Write the runbook**

Create `docs/supabase_image_retention_runbook.md` with these exact sections and commands:

- ownership and retention table;
- prerequisites and project-link verification;
- secret provisioning;
- dry-run invocation;
- controlled live test;
- Cron history query;
- Edge log inspection;
- rollback;
- secret rotation; and
- the rule that Render cutover waits for two successful scheduled invocations.

Include this observation query:

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
  select jobid from cron.job where jobname = 'cleanup-expired-images'
)
order by start_time desc
limit 10;
```

Include this rollback query:

```sql
select cron.unschedule(jobid)
from cron.job
where jobname = 'cleanup-expired-images';
```

State explicitly that rollback stops future schedules but does not restore already-deleted image objects; scan results remain available.

- [ ] **Step 2: Update README deployment documentation**

Add a concise “Image retention” subsection stating:

- Supabase owns scheduled cleanup;
- standard is seven days and demo is fifteen minutes;
- only Storage objects and the two path columns are removed;
- local checks are `deno test supabase/functions/cleanup-expired-images` and `pytest -q tests/test_supabase_retention_config.py`; and
- deployment/rollback steps live in `docs/supabase_image_retention_runbook.md`.

- [ ] **Step 3: Verify docs and all local tests**

Run:

```bash
rg -n "seven days|fifteen minutes|two successful|cron.unschedule" \
  README.md docs/supabase_image_retention_runbook.md
pytest -q
deno test supabase/functions/cleanup-expired-images
npm --prefix demo_site test -- --run
```

Expected: the required phrases are found and all Python, Deno, and frontend tests pass.

- [ ] **Step 4: Commit documentation**

```bash
git add README.md docs/supabase_image_retention_runbook.md
git commit -m "docs: add Supabase retention operations runbook"
```

### Task 6: Deploy safely to the MARKA Supabase project

**Files:**
- Apply: `migrations/002_add_scan_layout_mode.sql`
- Deploy: `supabase/functions/cleanup-expired-images/`
- Apply later: `supabase/migrations/20260915105434_schedule_image_retention.sql`

- [ ] **Step 1: Confirm management access to the exact MARKA project**

Run:

```bash
SUPABASE_ACCESS_TOKEN="$SUPABASE_ACCESS_TOKEN" npx supabase projects list
SUPABASE_ACCESS_TOKEN="$SUPABASE_ACCESS_TOKEN" \
  npx supabase link --project-ref tjdzldgccmnspanonthk
```

Expected: the project list contains `tjdzldgccmnspanonthk` and linking succeeds.

If the project is absent or linking fails, stop here. Do not deploy to another project. Request management access for the account that owns MARKA or authenticate the CLI with that account.

- [ ] **Step 2: Apply and verify the outstanding hand-drawn schema migration**

Run:

```bash
npx supabase db query --linked --file migrations/002_add_scan_layout_mode.sql
npx supabase db query --linked \
  --sql "select column_name, column_default from information_schema.columns where table_schema='public' and table_name='scans' and column_name='layout_mode';"
```

Expected: one `layout_mode` row with default `PRINTED_R07E`.

- [ ] **Step 3: Generate one secret without committing or printing it**

Run:

```bash
RETENTION_SECRET_FILE="$(mktemp)"
export RETENTION_SECRET_FILE
openssl rand -hex 32 > "$RETENTION_SECRET_FILE"
npx supabase secrets set --project-ref tjdzldgccmnspanonthk \
  CLEANUP_CRON_SECRET="$(<"$RETENTION_SECRET_FILE")"
```

Expected: Supabase confirms the Edge secret. Keep the temporary file only through the controlled verification.

- [ ] **Step 4: Store Cron inputs in Vault**

Run:

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

Expected: `vault.decrypted_secrets` contains one row named `project_url` and one named `cleanup_cron_secret`. Never paste their values into logs or commits.

- [ ] **Step 5: Deploy the function before enabling Cron**

Run:

```bash
npx supabase functions deploy cleanup-expired-images \
  --project-ref tjdzldgccmnspanonthk \
  --no-verify-jwt \
  --use-api
```

Expected: deployment succeeds for `cleanup-expired-images`.

- [ ] **Step 6: Perform authenticated dry run**

Run:

```bash
curl --fail-with-body --silent --show-error \
  -X POST \
  -H "Content-Type: application/json" \
  -H "X-Cleanup-Secret: $(<"$RETENTION_SECRET_FILE")" \
  -d '{"dry_run":true}' \
  https://tjdzldgccmnspanonthk.supabase.co/functions/v1/cleanup-expired-images
```

Expected: HTTP 200 with `"ok":true` and aggregate counts only. Confirm an incorrect secret returns 401.

- [ ] **Step 7: Run the isolated live reconciliation test**

Run this from the repository root. It creates a unique disabled test user, one
backdated scan, and two tiny objects; `finally` removes only those synthetic
resources even when an assertion fails.

```bash
python3 - <<'PY'
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from supabase import create_client

load_dotenv("api/.env")
url = os.environ["SUPABASE_URL"].rstrip("/")
service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
secret_file = os.environ["RETENTION_SECRET_FILE"]
with open(secret_file, encoding="utf-8") as handle:
    cleanup_secret = handle.read().strip()

client = create_client(url, service_key)
token = uuid.uuid4().hex
user_id = str(uuid.uuid4())
scan_row_id = str(uuid.uuid4())
scan_id = f"RETENTION-VERIFY-{token}"
marka_id = f"RV-{token[:16]}"
raw_path = f"retention-verification/{token}-raw.bin"
graded_path = f"retention-verification/{token}-graded.bin"
expected = {
    "score": 3,
    "total": 4,
    "percentage": 75,
    "raw_marks": {"1": "A"},
    "status": "completed",
    "user_id": user_id,
}


def invoke(dry_run):
    request = Request(
        f"{url}/functions/v1/cleanup-expired-images",
        data=json.dumps({"dry_run": dry_run}).encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Cleanup-Secret": cleanup_secret,
        },
    )
    with urlopen(request, timeout=90) as response:
        return json.loads(response.read())


def object_exists(bucket, path):
    folder, name = path.rsplit("/", 1)
    objects = client.storage.from_(bucket).list(folder)
    return any(item.get("name") == name for item in objects)


try:
    client.table("users").insert({
        "id": user_id,
        "marka_id": marka_id,
        "pin_hash": "disabled-retention-verification-user",
        "credits": 0,
    }).execute()
    client.storage.from_("raw_images").upload(
        raw_path,
        b"raw-retention-verification",
        {"content-type": "application/octet-stream", "upsert": "false"},
    )
    client.storage.from_("graded_images").upload(
        graded_path,
        b"graded-retention-verification",
        {"content-type": "application/octet-stream", "upsert": "false"},
    )
    client.table("scans").insert({
        "id": scan_row_id,
        "user_id": user_id,
        "scan_id": scan_id,
        "layout_mode": "PRINTED_R07E",
        **expected,
        "image_path": raw_path,
        "graded_image_path": graded_path,
        "created_at": (
            datetime.now(timezone.utc) - timedelta(days=8)
        ).isoformat(),
    }).execute()

    before = client.table("scans").select("*").eq(
        "id", scan_row_id
    ).single().execute().data
    dry = invoke(True)
    after_dry = client.table("scans").select("*").eq(
        "id", scan_row_id
    ).single().execute().data
    assert dry["dry_run"] is True
    assert dry["raw_paths_eligible"] >= 1
    assert dry["graded_paths_eligible"] >= 1
    assert after_dry["image_path"] == raw_path
    assert after_dry["graded_image_path"] == graded_path
    assert object_exists("raw_images", raw_path)
    assert object_exists("graded_images", graded_path)

    live = invoke(False)
    after_live = client.table("scans").select("*").eq(
        "id", scan_row_id
    ).single().execute().data
    assert live["ok"] is True
    assert after_live["image_path"] is None
    assert after_live["graded_image_path"] is None
    assert not object_exists("raw_images", raw_path)
    assert not object_exists("graded_images", graded_path)
    for column, value in expected.items():
        assert after_live[column] == value
    assert after_live["created_at"] == before["created_at"]
    assert token not in json.dumps(live)
    print(json.dumps(live, sort_keys=True))
finally:
    for bucket, path in (
        ("raw_images", raw_path),
        ("graded_images", graded_path),
    ):
        try:
            client.storage.from_(bucket).remove([path])
        except Exception:
            pass
    client.table("scans").delete().eq("id", scan_row_id).execute()
    client.table("users").delete().eq("id", user_id).execute()
PY
```

Expected: the script prints one aggregate cleanup report and exits zero. It
proves both test objects disappear, both image columns become null, the scan row
and assessment fields survive, dry run is non-mutating, and no test identifier
or object path appears in the function response. If it fails, do not enable
Cron; inspect Edge logs and keep the Render fallback.

- [ ] **Step 8: Enable the schedule only after the live test passes**

Run:

```bash
npx supabase db query --linked \
  --file supabase/migrations/20260915105434_schedule_image_retention.sql
npx supabase db query --linked \
  --sql "select jobid, jobname, schedule, active from cron.job where jobname='cleanup-expired-images';"
```

Expected: exactly one active job with schedule `*/15 * * * *`.

- [ ] **Step 9: Observe two scheduled runs**

Wait through at least two schedule boundaries, then execute the runbook history query.

Expected: the latest two runs show `succeeded` and Edge logs show 200 responses with aggregate data only. If either fails, unschedule immediately using the rollback query and keep the Render endpoint.

- [ ] **Step 10: Remove the temporary local secret**

Run:

```bash
shred -u "$RETENTION_SECRET_FILE"
unset RETENTION_SECRET_FILE
```

Expected: the temporary file no longer exists.

### Task 7: Cut scheduled retention over from Render

**Files:**
- Modify: `api/test_server.py`
- Modify: `api/server.py:907-963`
- Modify: `render.yaml:30-32`

- [ ] **Step 1: Write the failing route-removal test**

Append to `api/test_server.py`:

```python
def test_render_no_longer_exposes_scheduled_retention():
    paths = {route.path for route in server.app.routes}
    assert "/admin/wipe-expired" not in paths
    assert "/scans/{scan_id}/wipe-image" in paths
    assert "/scans/wipe-all-raw" in paths
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run:

```bash
pytest -q api/test_server.py::test_render_no_longer_exposes_scheduled_retention
```

Expected: FAIL because `/admin/wipe-expired` still exists.

- [ ] **Step 3: Remove only scheduled cleanup from Render**

Delete `wipe_expired_images` and `admin_wipe_expired` from `api/server.py`. Do not modify:

- the `finally` block that removes raw uploads after processing;
- `POST /scans/{scan_id}/wipe-image`;
- `DELETE /scans/{scan_id}`; or
- `POST /scans/wipe-all-raw`.

Remove only this block from `render.yaml`:

```yaml
      # Protects POST /admin/wipe-expired (daily 7-day image wipe).
      - key: CRON_SECRET
        sync: false
```

- [ ] **Step 4: Run backend and deployment tests**

Run:

```bash
pytest -q api/test_server.py tests/test_supabase_retention_config.py
pytest -q
```

Expected: all tests pass and no application reference to `CRON_SECRET` or `/admin/wipe-expired` remains.

- [ ] **Step 5: Commit the cutover**

```bash
git add api/server.py api/test_server.py render.yaml
git commit -m "refactor: retire Render scheduled image cleanup"
```

### Task 8: Final verification, push, and production smoke test

**Files:**
- Verify: all changed files
- Deploy through: existing Git push, Render auto-deploy, and Vercel workflow

- [ ] **Step 1: Run the full local verification suite**

Run:

```bash
deno fmt --check supabase/functions/cleanup-expired-images
deno lint supabase/functions/cleanup-expired-images
deno test supabase/functions/cleanup-expired-images
deno check supabase/functions/cleanup-expired-images/index.ts
pytest -q
npm --prefix demo_site test -- --run
npm --prefix demo_site run build
git diff --check
```

Expected: every command exits zero.

- [ ] **Step 2: Review the exact outgoing commits and files**

Run:

```bash
git status --short
git log --oneline origin/main..HEAD
git diff --stat origin/main...HEAD
```

Expected: only intentional MARKA work is committed. Leave unrelated pre-existing untracked files uncommitted.

- [ ] **Step 3: Push the verified branch**

Run:

```bash
git push origin main
```

Expected: the push succeeds and Render begins its configured auto-deploy.

- [ ] **Step 4: Smoke-test preserved and removed behavior**

After deployment:

```bash
curl --fail-with-body --silent --show-error \
  https://marka-api-e2kq.onrender.com/health
curl --silent --output /dev/null --write-out "%{http_code}\n" \
  -X POST https://marka-api-e2kq.onrender.com/admin/wipe-expired
```

Expected: health returns success and the removed route returns 404. Confirm a normal teacher scan still removes its raw upload immediately, the manual wipe route remains callable by its owner, and the next Supabase Cron history entry succeeds.

- [ ] **Step 5: Record the handoff**

In the deployment record, capture:

- Edge Function deployment timestamp;
- Cron `jobid`;
- the two observed successful run IDs;
- Render deploy identifier;
- live smoke-test time; and
- the maintainer responsible for secret rotation.

Do not record the cleanup secret, service-role key, object paths, user IDs, marks, or student data.
