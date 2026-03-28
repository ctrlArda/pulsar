create extension if not exists pgcrypto;

create table if not exists public.live_telemetry (
  observed_at timestamptz not null,
  mode text not null check (mode in ('live', 'archive')),
  solar_wind_speed double precision not null,
  bz double precision not null,
  bt double precision not null,
  density double precision not null,
  temperature double precision not null,
  kp_index double precision not null,
  estimated_kp double precision not null,
  xray_flux double precision not null,
  xray_class text not null,
  f107_flux double precision not null,
  cme_count integer not null default 0,
  early_detection boolean not null default false,
  eta_seconds integer,
  local_risk_percent double precision not null,
  local_magnetic_latitude double precision not null,
  auroral_expansion_percent double precision not null,
  ml_risk_percent double precision,
  ml_lead_time_minutes integer,
  summary_headline text not null,
  kp_history jsonb not null default '[]'::jsonb,
  power_lines jsonb not null default '{"type":"FeatureCollection","features":[]}'::jsonb,
  heat_grid jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  primary key (observed_at, mode)
);

create table if not exists public.crisis_alerts (
  id uuid primary key,
  created_at timestamptz not null default timezone('utc', now()),
  mode text not null check (mode in ('live', 'archive')),
  severity text not null check (severity in ('watch', 'warning', 'critical')),
  title text not null,
  subtitle text not null,
  eta_seconds integer,
  narrative text not null,
  telemetry jsonb not null,
  impacted_hardware jsonb not null default '[]'::jsonb,
  sop_actions jsonb not null default '[]'::jsonb
);

alter table public.live_telemetry enable row level security;
alter table public.crisis_alerts enable row level security;

drop policy if exists "public read live telemetry" on public.live_telemetry;
create policy "public read live telemetry"
on public.live_telemetry
for select
using (true);

drop policy if exists "public read crisis alerts" on public.crisis_alerts;
create policy "public read crisis alerts"
on public.crisis_alerts
for select
using (true);

create index if not exists idx_live_telemetry_created_at on public.live_telemetry (created_at desc);
create index if not exists idx_crisis_alerts_created_at on public.crisis_alerts (created_at desc);

do $$
begin
  if not exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'live_telemetry'
  ) then
    alter publication supabase_realtime add table public.live_telemetry;
  end if;

  if not exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'crisis_alerts'
  ) then
    alter publication supabase_realtime add table public.crisis_alerts;
  end if;
end $$;
