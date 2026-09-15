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
    standard: new Date(
      now.getTime() - 7 * 24 * 60 * 60 * 1000,
    ).toISOString(),
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
    if (request.method !== "POST") {
      return json({ error: "Method not allowed" }, 405);
    }
    if (!deps.secret) {
      return json({ error: "Configuration error" }, 500);
    }
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

  const scans = [
    ...new Map(
      [...demoRows, ...standardRows].map((scan) => [scan.id, scan]),
    ).values(),
  ];
  const raw = scans
    .filter((scan) => scan.image_path !== null)
    .map((scan) => ({ id: scan.id, path: scan.image_path as string }));
  const graded = scans
    .filter((scan) => scan.graded_image_path !== null)
    .map((scan) => ({
      id: scan.id,
      path: scan.graded_image_path as string,
    }));

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
  ): Promise<void> {
    for (const batch of chunks(objects, STORAGE_BATCH_SIZE)) {
      try {
        await store.removeObjects(
          bucket,
          batch.map((item) => item.path),
        );
      } catch {
        report.storage_failures += batch.length;
        continue;
      }
      try {
        await store.clearPaths(
          column,
          batch.map((item) => item.id),
        );
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
  report.ok = report.storage_failures === 0 &&
    report.metadata_failures === 0;
  return report;
}
