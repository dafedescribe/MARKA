import test from 'node:test';
import assert from 'node:assert/strict';

import {
  DEFAULT_SCAN_MODE,
  HANDDRAWN_A4_40_V1,
  buildProcessScanPayload,
  captureTipsForMode,
} from './scanModes.js';

test('printed R07-E remains the default', () => {
  assert.equal(DEFAULT_SCAN_MODE, 'PRINTED_R07E');
  assert.deepEqual(buildProcessScanPayload('scan-1', 'MATH'), {
    scan_id: 'scan-1', exam_code: 'MATH', layout_mode: 'PRINTED_R07E',
  });
});

test('hand-drawn mode is preserved in the process payload', () => {
  assert.equal(
    buildProcessScanPayload('scan-2', 'MATH', HANDDRAWN_A4_40_V1).layout_mode,
    'HANDDRAWN_A4_40_V1',
  );
});

test('unknown modes are rejected before upload processing', () => {
  assert.throws(
    () => buildProcessScanPayload('scan-3', 'MATH', 'AUTO_GUESS'),
    /Unsupported scan mode/,
  );
});

test('hand-drawn capture copy teaches X or tick instead of bubble shading', () => {
  const copy = captureTipsForMode(HANDDRAWN_A4_40_V1).map((tip) => tip.desc).join(' ');
  assert.match(copy, /X or tick/i);
  assert.doesNotMatch(copy, /fully shaded/i);
});
