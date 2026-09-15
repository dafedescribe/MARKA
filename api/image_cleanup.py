"""Small, retry-safe orchestration for user-triggered image cleanup."""

LAYERS = (
    ("raw_images", "image_path"),
    ("graded_images", "graded_image_path"),
)


def clear_image_layers(rows, remove_batch, clear_batch, batch_size=100):
    report = {"deleted": 0, "failed": 0}
    for bucket, column in LAYERS:
        items = [(row["id"], row.get(column)) for row in rows if row.get(column)]
        for offset in range(0, len(items), batch_size):
            batch = items[offset:offset + batch_size]
            paths = [path for _, path in batch]
            ids = [row_id for row_id, _ in batch]
            try:
                remove_batch(bucket, paths)
                clear_batch(column, ids)
                report["deleted"] += len(batch)
            except Exception:
                report["failed"] += len(batch)
    return report


def clear_user_image_library(client, user_id):
    rows = (
        client.table("scans")
        .select("id, image_path, graded_image_path")
        .eq("user_id", user_id)
        .execute()
        .data
        or []
    )

    def remove_batch(bucket, paths):
        client.storage.from_(bucket).remove(paths)

    def clear_batch(column, ids):
        client.table("scans").update({column: None}).in_("id", ids).execute()

    return clear_image_layers(rows, remove_batch, clear_batch)
