import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

// MARKA authenticates with its own backend-issued JWT, not Supabase Auth. We
// hand that token to supabase-js via the `accessToken` callback so every
// PostgREST / Storage / Realtime request is sent as the logged-in user and RLS
// returns their rows.
//
// The previous approach — supabase.auth.setSession({ access_token, refresh_token: '' })
// — FAILED with "Auth session missing!" because the refresh token was empty, then
// silently fell back to the anon role. Reads returned 0 rows with no error, so the
// OMR Library showed "No scans found" even though grading succeeded and the graded
// image was in storage. Never reintroduce setSession here.
let _accessToken = null
export const setSupabaseToken = (t) => { _accessToken = t || null }

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  accessToken: async () => _accessToken,
})
