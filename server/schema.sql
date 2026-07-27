-- Supabase SQL Editor 에 그대로 붙여넣기

create table if not exists public.claude_cooldown (
  key              text primary key,
  five_hour_pct    numeric,
  five_hour_reset  text,
  seven_day_pct    numeric,
  seven_day_reset  text,
  updated_at       timestamptz not null default now()
);

-- RLS 켜고 정책은 만들지 않습니다.
-- → anon/authenticated 키로는 아무것도 못 읽고 못 씁니다.
-- → API 라우트의 service_role 키만 통과합니다 (RLS 우회).
alter table public.claude_cooldown enable row level security;

-- 2주 넘게 안 올라온 행 정리용 (Supabase > Database > Cron 에서 주 1회)
-- delete from public.claude_cooldown where updated_at < now() - interval '14 days';
