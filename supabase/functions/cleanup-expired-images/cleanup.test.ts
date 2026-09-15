import {
  type Bucket,
  type CleanupReport,
  type CleanupStore,
  type Cohort,
  createCleanupHandler,
  type PathColumn,
  retentionCutoffs,
  runCleanup,
  type ScanRow,
} from "./cleanup.ts";

interface CandidateCall {
  cohort: Cohort;
  cutoff: string;
  demoUserId: string | null;
  limit: number;
}

class FakeStore implements CleanupStore {
  demoUserId: string | null = "demo-user";
  rows: Record<Cohort, ScanRow[]> = { demo: [], standard: [] };
  candidateCalls: CandidateCall[] = [];
  removed: Array<{ bucket: Bucket; paths: string[] }> = [];
  cleared: Array<{ column: PathColumn; ids: string[] }> = [];
  failingBucket: Bucket | null = null;
  failMetadata = false;

  findDemoUserId(): Promise<string | null> {
    return Promise.resolve(this.demoUserId);
  }

  listCandidates(args: CandidateCall): Promise<ScanRow[]> {
    this.candidateCalls.push(args);
    return Promise.resolve(this.rows[args.cohort]);
  }

  removeObjects(bucket: Bucket, paths: string[]): Promise<void> {
    if (this.failingBucket === bucket) {
      return Promise.reject(new Error("storage"));
    }
    this.removed.push({ bucket, paths });
    return Promise.resolve();
  }

  clearPaths(column: PathColumn, ids: string[]): Promise<void> {
    if (this.failMetadata) return Promise.reject(new Error("metadata"));
    this.cleared.push({ column, ids });
    return Promise.resolve();
  }
}

function row(
  id: string,
  raw: string | null,
  graded: string | null,
): ScanRow {
  return {
    id,
    user_id: "standard-user",
    image_path: raw,
    graded_image_path: graded,
    created_at: "2026-09-01T00:00:00.000Z",
  };
}

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
    cleanup: () => {
      calls += 1;
      return Promise.resolve({} as CleanupReport);
    },
  });
  const response = await handler(
    new Request("http://local", { method: "POST" }),
  );
  if (response.status !== 500 || calls !== 0) throw new Error("unsafe request");
});

Deno.test("incorrect secret returns 401 before cleanup", async () => {
  let calls = 0;
  const handler = createCleanupHandler({
    secret: "correct",
    cleanup: () => {
      calls += 1;
      return Promise.resolve({} as CleanupReport);
    },
  });
  const response = await handler(
    new Request("http://local", {
      method: "POST",
      headers: { "X-Cleanup-Secret": "wrong" },
    }),
  );
  if (response.status !== 401 || calls !== 0) throw new Error("unsafe request");
});

Deno.test("authenticated dry run reaches cleanup once", async () => {
  let dryRun: boolean | undefined;
  const report: CleanupReport = {
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
    cleanup: (value) => {
      dryRun = value;
      return Promise.resolve(report);
    },
  });
  const response = await handler(
    new Request("http://local", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Cleanup-Secret": "correct",
      },
      body: JSON.stringify({ dry_run: true }),
    }),
  );
  if (response.status !== 200 || dryRun !== true) {
    throw new Error("bad request");
  }
});

Deno.test("cleanup removes both layers and clears only their path columns", async () => {
  const store = new FakeStore();
  store.rows.standard = [row("one", "raw/one.jpg", "graded/one.jpg")];

  const report = await runCleanup(
    store,
    false,
    new Date("2026-09-15T12:00:00.000Z"),
  );

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

  const report = await runCleanup(
    store,
    true,
    new Date("2026-09-15T12:00:00.000Z"),
  );

  if (!report.dry_run || report.raw_paths_eligible !== 1) {
    throw new Error("bad report");
  }
  if (store.removed.length || store.cleared.length) {
    throw new Error("dry run mutated");
  }
});

Deno.test("storage failure leaves only matching paths available for retry", async () => {
  const store = new FakeStore();
  store.rows.standard = [row("one", "raw/one.jpg", "graded/one.jpg")];
  store.failingBucket = "raw_images";

  const report = await runCleanup(
    store,
    false,
    new Date("2026-09-15T12:00:00.000Z"),
  );

  if (report.raw_paths_cleared !== 0 || report.storage_failures !== 1) {
    throw new Error("raw failure was hidden");
  }
  if (report.graded_paths_cleared !== 1) {
    throw new Error("independent bucket stopped");
  }
  if (store.cleared.some((call) => call.column === "image_path")) {
    throw new Error("failed raw metadata was cleared");
  }
});

Deno.test("metadata failure is reported after Storage succeeds", async () => {
  const store = new FakeStore();
  store.rows.standard = [row("one", "raw/one.jpg", null)];
  store.failMetadata = true;

  const report = await runCleanup(
    store,
    false,
    new Date("2026-09-15T12:00:00.000Z"),
  );

  if (store.removed.length !== 1) throw new Error("object was not removed");
  if (report.metadata_failures !== 1 || report.ok) {
    throw new Error("metadata failure was hidden");
  }
});

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

Deno.test("missing demo user leaves all candidates on standard retention", async () => {
  const store = new FakeStore();
  store.demoUserId = null;
  store.rows.standard = [row("one", "raw/one.jpg", null)];

  const report = await runCleanup(
    store,
    true,
    new Date("2026-09-15T12:00:00.000Z"),
  );

  if (report.demo_user_found) throw new Error("demo user incorrectly found");
  if (store.candidateCalls.some((call) => call.cohort === "demo")) {
    throw new Error("unsafe demo query");
  }
  if (report.scans_inspected !== 1) throw new Error("standard scan skipped");
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
