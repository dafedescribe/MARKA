import test from 'node:test';
import assert from 'node:assert/strict';

import { storedImageCount, visibleLibraryScans } from './library.js';

const scans = [
  { scan_id: 'live', graded_image_path: 'u/live.webp' },
  { scan_id: 'expired', graded_image_path: null },
  { scan_id: 'raw-only', image_path: 'u/raw.jpg', graded_image_path: null },
];

test('Library shows only scans with an available graded image', () => {
  assert.deepEqual(
    visibleLibraryScans(scans).map((scan) => scan.scan_id),
    ['live'],
  );
});

test('stored image count reflects both storage layers', () => {
  assert.equal(storedImageCount(scans), 2);
});
