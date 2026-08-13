// app/api/remote/route.ts  (Next.js App Router)
//
// 원격 대기(클로드 코드 `claude rc`)를 **폰에서 켜고 끄기** 위한 중계.
// 사용량(/api/cooldown)과 방향이 반대다 — 이쪽은 폰이 쓰고 PC 가 읽는다.
//
//   폰  ──POST {key, want:"on"|"off"}──▶  rcw:<해시>      (원하는 상태)
//   PC  ──GET  ?key=…────────────────▶  둘 다 읽어감
//   PC  ──POST {key, state:"on"|"off"|"fail"}──▶  rcs:<해시>  (지금 상태)
//   폰  ──GET  ?key=…────────────────▶  state 를 보고 화면에 표시
//
// ★ **`/api/cooldown` 은 건드리지 않는다.** 폰에 이미 깔린 앱이 그 주소·경로·응답
//   일곱 필드에 맞춰져 있어서, 거기에 필드를 더하거나 고치면 전부 재페어링이다.
//   그래서 기능을 더할 때는 이렇게 **새 주소**를 판다.
//
// ★ '명령 큐' 가 아니라 **원하는 상태(want)** 다 — 같은 값이 여러 번 와도 탈이 없고,
//   PC 가 잠깐 꺼져 있다 켜져도 마지막으로 원한 상태를 그대로 따라간다.
//   (한 번 쓰고 지우는 큐로 만들면 PC 가 꺼져 있는 동안 누른 것이 증발한다)
//
// 저장·환경변수는 /api/cooldown 과 같다. 자세한 것은 server/README.md

import { NextRequest, NextResponse } from "next/server";
import { createHash } from "node:crypto";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const REST_URL = process.env.UPSTASH_REDIS_REST_URL ?? process.env.KV_REST_API_URL ?? "";
const REST_TOKEN = process.env.UPSTASH_REDIS_REST_TOKEN ?? process.env.KV_REST_API_TOKEN ?? "";

const WANT_TTL_SEC = 30 * 24 * 60 * 60; // 원하는 상태는 오래 둔다 (설정에 가깝다)
const STATE_TTL_SEC = 14 * 24 * 60 * 60; // 지금 상태는 사용량과 같은 14일
const STALE_MIN = 20; // 이보다 오래된 상태면 'PC 가 안 올리고 있다' 로 본다
const VALID_KEY = /^[0-9a-f]{32}$/;
const NO_STORE = { "Cache-Control": "no-store" };

// 저장소에는 key 원문을 두지 않는다 (읽기 비밀번호). /api/cooldown 과 같은 규칙.
function slot(prefix: string, key: string): string {
  return prefix + createHash("sha256").update(key).digest("hex");
}

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

function str(v: unknown): string | null {
  return typeof v === "string" && v.length <= 64 ? v : null;
}

type Stamped = { v: string; at: string };

function parse(raw: unknown): Stamped | null {
  if (typeof raw !== "string") return null;
  try {
    const o = JSON.parse(raw) as Stamped;
    return typeof o?.v === "string" && typeof o?.at === "string" ? o : null;
  } catch {
    return null;
  }
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

  const want = str(body.want);
  const state = str(body.state);

  // 한 번에 하나만 쓴다 — 폰은 want 를, PC 는 state 를 올린다.
  let cmd: (string | number)[];
  if (want !== null) {
    if (want !== "on" && want !== "off") {
      return NextResponse.json({ error: "bad want" }, { status: 400, headers: NO_STORE });
    }
    const row: Stamped = { v: want, at: new Date().toISOString() };
    cmd = ["SET", slot("rcw:", key), JSON.stringify(row), "EX", WANT_TTL_SEC];
  } else if (state !== null) {
    if (state !== "on" && state !== "off" && state !== "fail") {
      return NextResponse.json({ error: "bad state" }, { status: 400, headers: NO_STORE });
    }
    const row: Stamped = { v: state, at: new Date().toISOString() };
    cmd = ["SET", slot("rcs:", key), JSON.stringify(row), "EX", STATE_TTL_SEC];
  } else {
    return NextResponse.json({ error: "want or state" }, { status: 400, headers: NO_STORE });
  }

  try {
    await redis(cmd);
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
    // MGET 은 **명령 하나**다 — PC 가 주기적으로 부르는 자리라 여기서 두 번 부르면
    // 무료 한도(월 50만 명령) 계산이 그대로 두 배가 된다. server/README.md 참고.
    raw = await redis(["MGET", slot("rcw:", key), slot("rcs:", key)]);
  } catch {
    return NextResponse.json({ error: "db" }, { status: 500, headers: NO_STORE });
  }

  const pair = Array.isArray(raw) ? raw : [null, null];
  const want = parse(pair[0]);
  const state = parse(pair[1]);

  // 아직 아무도 안 쓴 키는 404 가 아니라 **빈 값**이다 — 처음 켠 폰·PC 가
  // 오류로 읽지 않게. (사용량 쪽은 값이 없으면 정말 없는 것이라 404 를 준다)
  const ageMin = state ? (Date.now() - new Date(state.at).getTime()) / 60000 : null;

  return NextResponse.json(
    {
      want: want?.v ?? null,
      want_at: want?.at ?? null,
      state: state?.v ?? null,
      state_at: state?.at ?? null,
      stale: ageMin === null ? true : ageMin > STALE_MIN,
    },
    { headers: NO_STORE }
  );
}
