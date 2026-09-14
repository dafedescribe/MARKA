# MARKA R07 Field Validation Protocol

## Decision to validate

Does R07 preserve the scan reliability of R06 while making the sheet cleaner and less dependent on machine geometry? The test is specifically about registration and timing geometry; it is not a validation of question content or handwriting recognition.

## Variants

| Variant | Registration | Timing | Purpose |
| --- | --- | --- | --- |
| A — corners only | 4 required corner ArUcos | None | Minimum viable geometry |
| B — R07-E reduced | 4 required corners + 4 optional 6 mm midpoints | 40 shared row marks | Proposed production design |
| C — R06 full | 9 required 7.5 mm ArUcos | 100 column-local marks | Reliability ceiling / control |

R07-E has 48 machine elements versus R06’s 109. Using marker bounding area plus timing-bar area as a consistent print-density proxy, R07-E uses about 457 mm² versus 836.25 mm² for R06—a 45.4% reduction. This is a geometry comparison, not a claim about exact toner consumption.

## Sample

Use 10 answer patterns spanning blank questions, single marks, light marks, erasures, and double marks. Print every pattern in all three variants from the same printer and paper batch at 100% scale. This produces 30 completed forms and keeps ground truth identical across variants.

Capture each form once in each condition:

1. Flat, evenly lit, camera parallel.
2. Rotated 15–25 degrees.
3. Strong side shadow across the answer grid.
4. One horizontal fold through the grid.
5. Curled by holding only the short edges.

The minimum run is therefore 150 images. Randomize variant order and use the same phone, distance range, and capture operator. Keep the original images; do not crop or enhance them manually.

## Measurements

For every image, record:

- variant and condition;
- whether the first scan completed;
- required and optional anchors detected;
- registration mode and optional-anchor residual;
- timing marks expected and detected;
- answer accuracy against ground truth;
- false mark, missed mark, and wrong-option counts;
- processing time;
- whether a manual retry was needed.

After the scan exercise, show the three blank forms without labels to at least 10 users and ask which looks clearest, which feels most credible, and whether any machine marks are distracting.

## Retain / remove gates

Retain R07-E as the production candidate only if all are true:

- overall answer accuracy is no more than 0.5 percentage points below R06;
- first-scan success and manual retry rate are no worse than R06;
- processing time is no slower than R06 at the median;
- the machine-geometry area proxy is at least 20% lower than R06;
- at least 60% of users prefer R07 or rate it equal to the cleanest alternative.

Retain the four optional midpoint anchors only if, in folded and curled conditions, they improve accuracy by at least 1 percentage point or reduce retries by at least 20% relative to corners-only. If they do not cross either gate, remove them in R08.

Retain shared timing marks only if they improve shadow/fold accuracy or retry rate over corners-only without creating a measurable false-mark increase. If only one rail contributes, test a 20-mark single-rail R08 candidate.

## Reporting

Report results by condition as well as overall. A strong flat-sheet average must not hide a fold or curl failure. Include representative failure images and the scanner diagnostic object for every retry. End with one decision: retain R07, simplify further, or restore a specific R06 element.
