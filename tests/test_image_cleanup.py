from api.image_cleanup import clear_image_layers


def test_clear_image_layers_deletes_both_buckets_and_clears_matching_columns():
    rows = [
        {"id": "1", "image_path": "u/1.jpg", "graded_image_path": "u/1.webp"},
        {"id": "2", "image_path": None, "graded_image_path": "u/2.webp"},
    ]
    removed = []
    cleared = []

    report = clear_image_layers(
        rows,
        lambda bucket, paths: removed.append((bucket, paths)),
        lambda column, ids: cleared.append((column, ids)),
    )

    assert removed == [
        ("raw_images", ["u/1.jpg"]),
        ("graded_images", ["u/1.webp", "u/2.webp"]),
    ]
    assert cleared == [
        ("image_path", ["1"]),
        ("graded_image_path", ["1", "2"]),
    ]
    assert report == {"deleted": 3, "failed": 0}


def test_clear_image_layers_keeps_failed_bucket_paths_retryable():
    rows = [{"id": "1", "image_path": "u/1.jpg", "graded_image_path": "u/1.webp"}]
    cleared = []

    def remove(bucket, _paths):
        if bucket == "graded_images":
            raise RuntimeError("storage unavailable")

    report = clear_image_layers(
        rows,
        remove,
        lambda column, ids: cleared.append((column, ids)),
    )

    assert cleared == [("image_path", ["1"])]
    assert report == {"deleted": 1, "failed": 1}


def test_clear_image_layers_batches_at_one_hundred():
    rows = [
        {"id": str(index), "image_path": f"u/{index}.jpg", "graded_image_path": None}
        for index in range(205)
    ]
    batches = []

    clear_image_layers(
        rows,
        lambda _bucket, paths: batches.append(paths),
        lambda _column, _ids: None,
    )

    assert [len(batch) for batch in batches] == [100, 100, 5]
