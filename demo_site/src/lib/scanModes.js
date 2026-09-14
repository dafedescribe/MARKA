export const PRINTED_R07E = 'PRINTED_R07E';
export const HANDDRAWN_A4_40_V1 = 'HANDDRAWN_A4_40_V1';
export const DEFAULT_SCAN_MODE = PRINTED_R07E;

const SUPPORTED_SCAN_MODES = new Set([PRINTED_R07E, HANDDRAWN_A4_40_V1]);

export function buildProcessScanPayload(scanId, examCode, layoutMode = DEFAULT_SCAN_MODE) {
  if (!SUPPORTED_SCAN_MODES.has(layoutMode)) {
    throw new Error(`Unsupported scan mode: ${layoutMode}`);
  }

  return {
    scan_id: scanId,
    exam_code: examCode,
    layout_mode: layoutMode,
  };
}

export function captureTipsForMode(layoutMode = DEFAULT_SCAN_MODE) {
  if (!SUPPORTED_SCAN_MODES.has(layoutMode)) {
    throw new Error(`Unsupported scan mode: ${layoutMode}`);
  }

  const markTip = layoutMode === HANDDRAWN_A4_40_V1
    ? { title: 'Use a clear X or tick', desc: 'One X or tick inside each chosen box' }
    : { title: 'Fill bubbles darkly', desc: 'Dark pencil or pen, fully shaded' };

  return [
    { title: 'Even, bright light', desc: 'No shadows across the sheet' },
    { title: 'Flat & fully in frame', desc: 'All 4 corner squares visible' },
    markTip,
    { title: 'Straight & in focus', desc: 'Shoot from directly above' },
  ];
}
