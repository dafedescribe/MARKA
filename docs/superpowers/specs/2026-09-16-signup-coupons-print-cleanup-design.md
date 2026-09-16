# Signup Coupons and Print Cleanup Design

## Goal

Let controlled marketing campaigns create payment-free accounts safely, while removing two valueless elements from branded printouts.

## Coupon flow

- Add an optional coupon field under the signup email. When present, submit to a dedicated coupon endpoint instead of opening checkout.
- A campaign stores a code hash, starting credits, maximum redemptions, current redemptions, expiry, and active state.
- One database transaction validates the campaign, reserves one redemption, creates the user, and records attribution. The existing unique email constraint prevents repeat free accounts.
- Normalize codes by trimming and uppercasing; rate-limit attempts and return one neutral invalid/expired/exhausted message.
- Do not add an admin interface. Marketing campaigns are inserted or disabled directly in Supabase.

## Initial campaigns

- `MARKA-LAUNCH50`: 50 credits, 100 uses, expires 2026-10-31.
- `MARKA-TEACHERS50`: 50 credits, 100 uses, expires 2026-10-31.
- `MARKA-SCHOOLS50`: 50 credits, 50 uses, expires 2026-10-31.
- Active codes are applied directly to Supabase and are not committed to Git.

## Print cleanup

- When a logo exists, draw only the logo; omit its outline. Keep the outline and placeholder when no logo exists.
- Remove the `MARKA ID / EXAM CODE` header text from the printed OMR. Existing student-information boxes remain unchanged.

## Verification

- Focused tests cover code normalization, expiry/usage rejection, and the atomic database contract.
- Existing signup, PDF generator, backend, frontend, and production-build checks guard regressions without adding snapshot-test overhead.
