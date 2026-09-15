ALTER TABLE public.users
ADD COLUMN IF NOT EXISTS sheet_profile JSONB NOT NULL DEFAULT '{}'::jsonb;
