import type { SupabaseClient } from "npm:@supabase/supabase-js@2.116.0";
import { SupabaseCleanupStore } from "./index.ts";

type Call = unknown[];
type Result = { data: unknown; error: Error | null };

function assertCall(calls: Call[], expected: Call): void {
  const wanted = JSON.stringify(expected);
  if (!calls.some((call) => JSON.stringify(call) === wanted)) {
    throw new Error(`missing call ${wanted}: ${JSON.stringify(calls)}`);
  }
}

function assertNoCall(calls: Call[], method: string): void {
  if (calls.some((call) => call[0] === method)) {
    throw new Error(`unexpected ${method}: ${JSON.stringify(calls)}`);
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

Deno.test("demo query is old-first, bounded, strict, and demo-scoped", async () => {
  const { client, calls } = fakeSupabase({ data: [], error: null });
  const store = new SupabaseCleanupStore(client);

  await store.listCandidates({
    cohort: "demo",
    cutoff: "2026-09-15T11:45:00.000Z",
    demoUserId: "demo-id",
    limit: 500,
  });

  assertCall(calls, ["from", "scans"]);
  assertCall(calls, [
    "select",
    "id,user_id,image_path,graded_image_path,created_at",
  ]);
  assertCall(calls, ["lt", "created_at", "2026-09-15T11:45:00.000Z"]);
  assertCall(calls, [
    "or",
    "image_path.not.is.null,graded_image_path.not.is.null",
  ]);
  assertCall(calls, ["eq", "user_id", "demo-id"]);
  assertCall(calls, ["order", "created_at", { ascending: true }]);
  assertCall(calls, ["limit", 500]);
});

Deno.test("standard query excludes demo when demo account exists", async () => {
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

Deno.test("standard query includes everyone when demo account is absent", async () => {
  const { client, calls } = fakeSupabase({ data: [], error: null });
  const store = new SupabaseCleanupStore(client);

  await store.listCandidates({
    cohort: "standard",
    cutoff: "2026-09-08T12:00:00.000Z",
    demoUserId: null,
    limit: 500,
  });

  assertNoCall(calls, "neq");
  assertNoCall(calls, "eq");
});

Deno.test("findDemoUserId uses the fixed MARKA demo identity", async () => {
  const { client, calls } = fakeSupabase({
    data: { id: "demo-id" },
    error: null,
  });
  const store = new SupabaseCleanupStore(client);

  const id = await store.findDemoUserId();

  if (id !== "demo-id") throw new Error("demo user not returned");
  assertCall(calls, ["from", "users"]);
  assertCall(calls, ["eq", "marka_id", "DEMO-TEST"]);
  assertCall(calls, ["maybeSingle"]);
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
