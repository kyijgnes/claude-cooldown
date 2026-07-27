// app/api/cooldown/route.ts  (Next.js App Router)
//
// POST : PC 에이전트가 사용률을 올림
// GET  : 폰 위젯(KWGT)이 ?key=... 로 읽어감
//
// 환경변수 (Vercel > Settings > Environment Variables)
//   NEXT_PUBLIC_SUPABASE_URL
//   SUPABASE_SERVICE_ROLE_KEY   ← 절대 클라이언트에 노출 금지

import { createClient } from "@supabase/supabase-js";
import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const db = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!,
  { auth: { persistSession: false } }
);

const VALID_KEY = /^[0-9a-f]{32}$/;

function num(v: unknown): number | null {
  return typeof v === "number" && isFinite(v) ? Math.max(0, Math.min(100, v)) : null;
}

function str(v: unknown): string | null {
  return typeof v === "string" && v.length <= 64 ? v : null;
}

export async function POST(req: NextRequest) {
  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "bad json" }, { status: 400 });
  }

  const key = str(body.key);
  if (!key || !VALID_KEY.test(key)) {
    return NextResponse.json({ error: "bad key" }, { status: 400 });
  }

  const row = {
    key,
    five_hour_pct: num(body.five_hour_pct),
    five_hour_reset: str(body.five_hour_reset),
    seven_day_pct: num(body.seven_day_pct),
    seven_day_reset: str(body.seven_day_reset),
    updated_at: new Date().toISOString(),
  };

  const { error } = await db.from("claude_cooldown").upsert(row, { onConflict: "key" });
  if (error) return NextResponse.json({ error: "db" }, { status: 500 });

  return NextResponse.json({ ok: true });
}

export async function GET(req: NextRequest) {
  const key = req.nextUrl.searchParams.get("key") ?? "";
  if (!VALID_KEY.test(key)) {
    return NextResponse.json({ error: "bad key" }, { status: 400 });
  }

  const { data, error } = await db
    .from("claude_cooldown")
    .select("five_hour_pct, five_hour_reset, seven_day_pct, seven_day_reset, updated_at")
    .eq("key", key)
    .maybeSingle();

  if (error) return NextResponse.json({ error: "db" }, { status: 500 });
  if (!data) return NextResponse.json({ error: "not found" }, { status: 404 });

  // 값이 20분 이상 안 올라왔으면 PC가 꺼진 상태 → 위젯에서 구분 가능하게
  const ageMin = (Date.now() - new Date(data.updated_at).getTime()) / 60000;

  return NextResponse.json(
    { ...data, stale: ageMin > 20, age_min: Math.round(ageMin) },
    { headers: { "Cache-Control": "no-store" } }
  );
}
