-- Crosshair Studio Premium code backend
-- Run this entire file in Supabase -> SQL Editor -> New query -> Run.
-- The client only receives permission to call these two RPC functions.
-- Premium code rows and entitlements are not directly readable by public clients.

create extension if not exists pgcrypto with schema extensions;

create table if not exists public.premium_codes (
    code_hash text primary key,
    is_active boolean not null default true,
    redeemed_at timestamptz,
    redeemed_device_id text,
    created_at timestamptz not null default now(),
    constraint premium_codes_redemption_pair check (
        (redeemed_at is null and redeemed_device_id is null)
        or
        (redeemed_at is not null and redeemed_device_id is not null)
    )
);

create table if not exists public.premium_entitlements (
    device_id text primary key,
    code_hash text not null unique references public.premium_codes(code_hash),
    activated_at timestamptz not null default now()
);

alter table public.premium_codes enable row level security;
alter table public.premium_entitlements enable row level security;

revoke all on table public.premium_codes from anon, authenticated;
revoke all on table public.premium_entitlements from anon, authenticated;

create or replace function public.redeem_premium_code(p_code text, p_device_id text)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_hash text;
begin
    if p_device_id is null or pg_catalog.length(pg_catalog.btrim(p_device_id)) < 16
       or p_code is null or pg_catalog.length(pg_catalog.btrim(p_code)) < 4 then
        return pg_catalog.jsonb_build_object('ok', false, 'message', 'Invalid code or device.');
    end if;

    if exists (
        select 1 from public.premium_entitlements e
        where e.device_id = p_device_id
    ) then
        return pg_catalog.jsonb_build_object('ok', true, 'already_active', true);
    end if;

    v_hash := pg_catalog.encode(
        extensions.digest(
            pg_catalog.convert_to(pg_catalog.lower(pg_catalog.btrim(p_code)), 'UTF8'),
            'sha256'
        ),
        'hex'
    );

    update public.premium_codes
       set redeemed_at = pg_catalog.now(),
           redeemed_device_id = p_device_id
     where code_hash = v_hash
       and is_active = true
       and redeemed_at is null
    returning code_hash into v_hash;

    if not found then
        return pg_catalog.jsonb_build_object(
            'ok', false,
            'message', 'That code is invalid or has already been redeemed.'
        );
    end if;

    insert into public.premium_entitlements (device_id, code_hash)
    values (p_device_id, v_hash);

    return pg_catalog.jsonb_build_object('ok', true, 'already_active', false);
end;
$$;

create or replace function public.check_premium(p_device_id text)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.premium_entitlements e
        where e.device_id = p_device_id
    );
$$;

revoke all on function public.redeem_premium_code(text, text) from public;
revoke all on function public.check_premium(text) from public;
grant execute on function public.redeem_premium_code(text, text) to anon, authenticated;
grant execute on function public.check_premium(text) to anon, authenticated;
