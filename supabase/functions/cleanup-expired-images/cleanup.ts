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
