// app/api/cooldown/route.ts  (Next.js App Router)
//
// POST : PC 위젯이 사용률을 올림 (같은 key 로 다시 오면 덮어쓴다)
// GET  : 폰 앱이 ?key=... 로 읽어감
//
// 저장소는 Upstash Redis. 값이 한 줄뿐이라 SDK 없이 REST 를 fetch 로 직접 부른다.
// 환경변수 (Vercel > Settings > Environment Variables)
//   UPSTASH_REDIS_REST_URL    (Vercel 마켓플레이스로 붙이면 KV_REST_API_URL 로 들어온다)
//   UPSTASH_REDIS_REST_TOKEN  (〃 KV_REST_API_TOKEN)   ← 절대 클라이언트에 노출 금지
// 저장소 만들기·배포·되돌리기는 server/README.md

import { NextRequest, NextResponse } from "next/server";
import { createHash } from "node:crypto";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const REST_URL = process.env.UPSTASH_REDIS_REST_URL ?? process.env.KV_REST_API_URL ?? "";
const REST_TOKEN = process.env.UPSTASH_REDIS_REST_TOKEN ?? process.env.KV_REST_API_TOKEN ?? "";

const TTL_SEC = 14 * 24 * 60 * 60; // 14일 동안 안 올라오면 저절로 사라진다
const STALE_MIN = 20; // 이보다 오래된 값이면 폰이 'PC 값 N분 전' 을 띄운다
const VALID_KEY = /^[0-9a-f]{32}$/;
const NO_STORE = { "Cache-Control": "no-store" };

type Row = {
  five_hour_pct: number | null;
  five_hour_reset: string | null;
  seven_day_pct: number | null;
  seven_day_reset: string | null;
  updated_at: string;
};

// 저장소에는 key 원문을 두지 않는다 — 읽기 비밀번호이기 때문.
// 해시는 단방향이라 값을 넣고 빼는 데는 지장이 없고, 저장소가 새도 남의 값을 읽을 수 없다.
function slot(key: string): string {
  return "cd:" + createHash("sha256").update(key).digest("hex");
}

// Upstash REST: 명령을 JSON 배열로 POST 하면 { result } 또는 { error } 가 온다.
// 던지는 메시지에 key·slot 을 담지 않는다 (Vercel 로그에 남는다).
async function redis(cmd: (string | number)[]): Promise<unknown> {
  if (!REST_URL || !REST_TOKEN) throw new Error("store env missing");

  const res = await fetch(REST_URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${REST_TOKEN}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(cmd),
    cache: "no-store",
  });

  const body = (await res.json().catch(() => null)) as { result?: unknown; error?: string } | null;
  if (!res.ok || !body || body.error) throw new Error(`store ${cmd[0]} failed`);
  return body.result ?? null;
}

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
    return NextResponse.json({ error: "bad json" }, { status: 400, headers: NO_STORE });
  }

  const key = str(body.key);
  if (!key || !VALID_KEY.test(key)) {
    return NextResponse.json({ error: "bad key" }, { status: 400, headers: NO_STORE });
  }

  const row: Row = {
    five_hour_pct: num(body.five_hour_pct),
    five_hour_reset: str(body.five_hour_reset),
    seven_day_pct: num(body.seven_day_pct),
    seven_day_reset: str(body.seven_day_reset),
    updated_at: new Date().toISOString(), // 서버가 찍는다 (클라이언트 값은 안 받는다)
  };

  try {
    // SET 은 덮어쓰기다 — 같은 key 로 다시 와도 행이 쌓이지 않는다.
    await redis(["SET", slot(key), JSON.stringify(row), "EX", TTL_SEC]);
  } catch {
    return NextResponse.json({ error: "db" }, { status: 500, headers: NO_STORE });
  }

  return NextResponse.json({ ok: true }, { headers: NO_STORE });
}

export async function GET(req: NextRequest) {
  const key = req.nextUrl.searchParams.get("key") ?? "";
  if (!VALID_KEY.test(key)) {
    return NextResponse.json({ error: "bad key" }, { status: 400, headers: NO_STORE });
  }

  let raw: unknown;
  try {
    raw = await redis(["GET", slot(key)]);
  } catch {
    return NextResponse.json({ error: "db" }, { status: 500, headers: NO_STORE });
  }

  // 없는 키 · 14일이 지나 만료된 키 → 둘 다 null 이 온다
  if (typeof raw !== "string") {
    return NextResponse.json({ error: "not found" }, { status: 404, headers: NO_STORE });
  }

  let row: Row;
  try {
    row = JSON.parse(raw) as Row;
  } catch {
    return NextResponse.json({ error: "db" }, { status: 500, headers: NO_STORE });
  }

  // 값이 20분 이상 안 올라왔으면 PC 가 꺼진 상태 → 폰에서 구분 가능하게
  const ageMin = (Date.now() - new Date(row.updated_at).getTime()) / 60000;

  return NextResponse.json(
    { ...row, stale: ageMin > STALE_MIN, age_min: Math.round(ageMin) },
    { headers: NO_STORE }
  );
}
