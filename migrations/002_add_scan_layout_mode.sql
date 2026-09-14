ALTER TABLE public.scans
ADD COLUMN IF NOT EXISTS layout_mode VARCHAR NOT NULL DEFAULT 'PRINTED_R07E';

ALTER TABLE public.scans
DROP CONSTRAINT IF EXISTS scans_layout_mode_check;

ALTER TABLE public.scans
ADD CONSTRAINT scans_layout_mode_check
CHECK (layout_mode IN ('PRINTED_R07E', 'HANDDRAWN_A4_40_V1'));
