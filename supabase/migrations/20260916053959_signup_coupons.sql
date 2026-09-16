CREATE TABLE IF NOT EXISTS public.coupon_campaigns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code_hash TEXT NOT NULL UNIQUE,
  credits INTEGER NOT NULL CHECK (credits > 0),
  max_redemptions INTEGER NOT NULL CHECK (max_redemptions > 0),
  redemption_count INTEGER NOT NULL DEFAULT 0 CHECK (redemption_count >= 0),
  expires_at TIMESTAMPTZ NOT NULL,
  active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (redemption_count <= max_redemptions)
);

CREATE TABLE IF NOT EXISTS public.coupon_redemptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  coupon_id UUID NOT NULL REFERENCES public.coupon_campaigns(id),
  user_id UUID NOT NULL REFERENCES public.users(id),
  email TEXT NOT NULL,
  redeemed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (coupon_id, email)
);

ALTER TABLE public.coupon_campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.coupon_redemptions ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.coupon_campaigns FROM PUBLIC, anon, authenticated;
REVOKE ALL ON public.coupon_redemptions FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.coupon_campaigns TO service_role;
GRANT SELECT, INSERT ON public.coupon_redemptions TO service_role;

CREATE OR REPLACE FUNCTION public.redeem_signup_coupon(
  p_code_hash TEXT,
  p_email TEXT,
  p_marka_id TEXT,
  p_pin_hash TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = ''
AS $$
DECLARE
  campaign public.coupon_campaigns%ROWTYPE;
  created_user_id UUID;
  normalized_email TEXT := lower(trim(p_email));
BEGIN
  SELECT * INTO campaign
  FROM public.coupon_campaigns
  WHERE code_hash = p_code_hash
  FOR UPDATE;

  IF NOT FOUND OR NOT campaign.active OR campaign.expires_at <= now()
     OR campaign.redemption_count >= campaign.max_redemptions THEN
    RAISE EXCEPTION 'coupon_unavailable' USING ERRCODE = 'P0001';
  END IF;

  INSERT INTO public.users (marka_id, pin_hash, email, credits)
  VALUES (p_marka_id, p_pin_hash, normalized_email, campaign.credits)
  RETURNING id INTO created_user_id;

  UPDATE public.coupon_campaigns
  SET redemption_count = redemption_count + 1
  WHERE id = campaign.id;

  INSERT INTO public.coupon_redemptions (coupon_id, user_id, email)
  VALUES (campaign.id, created_user_id, normalized_email);

  RETURN jsonb_build_object(
    'user_id', created_user_id,
    'credits', campaign.credits
  );
END;
$$;

REVOKE EXECUTE ON FUNCTION public.redeem_signup_coupon(TEXT, TEXT, TEXT, TEXT)
FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.redeem_signup_coupon(TEXT, TEXT, TEXT, TEXT)
TO service_role;
