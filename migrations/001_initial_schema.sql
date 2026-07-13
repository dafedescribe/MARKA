-- =====================================================================
-- MARKA Database Schema — Version-controlled migration
-- Run against a fresh Supabase project to recreate the full schema.
-- =====================================================================

-- ── Tables ───────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.users (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  marka_id   VARCHAR NOT NULL UNIQUE,
  pin_hash   VARCHAR NOT NULL,
  email      VARCHAR UNIQUE,
  credits    INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.exams (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID REFERENCES public.users(id),
  exam_code  VARCHAR NOT NULL,
  answer_key JSONB,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (user_id, exam_code)
);

CREATE TABLE IF NOT EXISTS public.scans (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           UUID REFERENCES public.users(id),
  exam_id           UUID REFERENCES public.exams(id),
  scan_id           VARCHAR NOT NULL UNIQUE,
  status            VARCHAR DEFAULT 'processing',
  score             INTEGER,
  total             INTEGER,
  percentage        NUMERIC,
  raw_marks         JSONB,
  image_path        TEXT,
  graded_image_path TEXT,
  error_message     TEXT,
  created_at        TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.transactions (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  reference     VARCHAR NOT NULL UNIQUE,
  marka_id      VARCHAR NOT NULL,
  amount        NUMERIC NOT NULL,
  credits_added INTEGER NOT NULL,
  created_at    TIMESTAMPTZ DEFAULT now()
);


-- ── RPC Functions (atomic credit operations) ─────────────────────────

CREATE OR REPLACE FUNCTION deduct_credit(user_uuid UUID)
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
  new_credits INT;
BEGIN
  UPDATE users
  SET credits = credits - 1
  WHERE id = user_uuid AND credits > 0
  RETURNING credits INTO new_credits;
  RETURN new_credits;
END;
$$;

CREATE OR REPLACE FUNCTION add_credits_by_marka_id(m_id TEXT, amount INT)
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
  new_credits INT;
BEGIN
  UPDATE users
  SET credits = credits + amount
  WHERE marka_id = m_id
  RETURNING credits INTO new_credits;
  RETURN new_credits;
END;
$$;


-- ── RLS Helper ───────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.marka_uid()
RETURNS uuid
LANGUAGE sql STABLE
AS $$
  SELECT COALESCE(
    auth.uid(),
    (current_setting('request.jwt.claims', true)::jsonb ->> 'sub')::uuid
  );
$$;


-- ── Row Level Security ───────────────────────────────────────────────

ALTER TABLE public.users        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.exams        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scans        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transactions ENABLE ROW LEVEL SECURITY;

-- users: read own row only
CREATE POLICY "users_select_own" ON public.users
  FOR SELECT USING (id = public.marka_uid());

-- exams: full CRUD on own rows
CREATE POLICY "exams_select_own" ON public.exams
  FOR SELECT USING (user_id = public.marka_uid());
CREATE POLICY "exams_insert_own" ON public.exams
  FOR INSERT WITH CHECK (user_id = public.marka_uid());
CREATE POLICY "exams_update_own" ON public.exams
  FOR UPDATE USING (user_id = public.marka_uid());

-- scans: read + insert + update own
CREATE POLICY "scans_select_own" ON public.scans
  FOR SELECT USING (user_id = public.marka_uid());
CREATE POLICY "scans_insert_own" ON public.scans
  FOR INSERT WITH CHECK (user_id = public.marka_uid());
CREATE POLICY "scans_update_own" ON public.scans
  FOR UPDATE USING (user_id = public.marka_uid());

-- transactions: no client access (service_role only)
-- RLS is ON with zero policies = fully locked. Intentional.
