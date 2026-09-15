import {
  type CleanupReport,
  createCleanupHandler,
  retentionCutoffs,
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
