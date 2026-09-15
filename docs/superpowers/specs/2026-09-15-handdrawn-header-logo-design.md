# Hand-drawn Header and Reusable Logo Design

## Goal

Make the hand-drawn objective layout unmistakable for young learners and let a teacher upload one reusable logo for printed sheets and result receipts.

## Hand-drawn geometry

- Keep the four registration anchors and the 15 cm × 2 cm Name/Class/Subject strip unchanged.
- Add a ruled 1 cm header directly above each objective grid: blank question-number cell, then A, B, C, D, E in five separate cells.
- Place the identity strip at 30–50 mm, the letter header at 50–60 mm, and the 20 answer rows at 60–260 mm.
- The scanner reads only the 20 answer rows. The header is a construction and comprehension aid, not an answer row.
- Update the profile, guide, synthetic fixtures, and scanner geometry together so drawing and detection cannot drift.

## Logo flow

- Add Upload, Preview, Replace, and Remove controls to the existing sheet-details card.
- Accept PNG, JPEG, or WebP up to 2 MB.
- Validate and normalize server-side to a maximum 256 px WebP, then store the small data URL inside the user's existing private `sheet_profile` JSON.
- Render the normalized logo in the existing logo boxes on printed OMR sheets and receipts. Missing or invalid logos retain the current placeholder.
- Do not create another Storage bucket, policy set, or cleanup lifecycle for this single small account asset.

## Errors and security

- Reject unsupported, unreadable, oversized, or post-compression-over-limit files with a clear 4xx response.
- Logo updates remain authenticated and scoped to the current user's profile row.
- Profile text updates preserve the server-managed logo value; removing the logo clears only that value.

## Verification

- One geometry test proves the separated header and shifted 20-row answer bounds.
- One logo normalization test covers valid and invalid input.
- Existing scanner, receipt, frontend, and build suites guard regressions; no redundant UI snapshot suite is added.
