import {
  createClient,
  type SupabaseClient,
} from "npm:@supabase/supabase-js@2.116.0";
import {
  type Bucket,
  type CleanupStore,
  type Cohort,
  createCleanupHandler,
  type PathColumn,
  runCleanup,
  type ScanRow,
} from "./cleanup.ts";

interface Environment {
  get(key: string): string | undefined;
}

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

export function buildHandler(env: Environment = Deno.env) {
  const secret = env.get("CLEANUP_CRON_SECRET") ?? "";
  if (!secret) {
    console.error(
      "Missing required environment variable: CLEANUP_CRON_SECRET",
    );
  }

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

      const store = new SupabaseCleanupStore(
        createClient(url, serviceRoleKey),
      );
      const report = await runCleanup(store, dryRun);
      console.log(JSON.stringify(report));
      return report;
    },
  });
}

if (import.meta.main) {
  Deno.serve(buildHandler());
}
