// server/relay_check.mjs — 릴레이가 폰과 맺은 약속을 지키는지 확인한다.
//
//   node relay_check.mjs https://<내-릴레이>.vercel.app
//   node relay_check.mjs                     (주소 없으면 http://localhost:3000)
//
// 저장소를 또 갈아치울 일이 생기면 이 파일이 합격 기준이다.
// 마지막 '오래된 값' 항목만 저장소를 직접 건드리므로, 환경변수가 있을 때만 돈다:
//   UPSTASH_REDIS_REST_URL=... UPSTASH_REDIS_REST_TOKEN=... node relay_check.mjs <주소>

import { createHash } from "node:crypto";

const BASE = (process.argv[2] ?? "http://localhost:3000").replace(/\/+$/, "");
const API = `${BASE}/api/cooldown`;
const KEY = createHash("sha256").update("relay_check").digest("hex").slice(0, 32);
const GHOST = "f".repeat(32); // 저장한 적 없는 키

const REST_URL = process.env.UPSTASH_REDIS_REST_URL ?? process.env.KV_REST_API_URL ?? "";
const REST_TOKEN = process.env.UPSTASH_REDIS_REST_TOKEN ?? process.env.KV_REST_API_TOKEN ?? "";

let failed = 0;

function ok(pass, label, detail = "") {
  if (!pass) failed++;
  console.log(`${pass ? "  통과" : "  실패"}  ${label}${detail ? `  — ${detail}` : ""}`);
}

function post(body) {
  return fetch(API, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

const sample = (pct) => ({
  key: KEY,
  five_hour_pct: pct,
  five_hour_reset: "2026-07-31T22:19:59+00:00",
  seven_day_pct: 55,
  seven_day_reset: "2026-08-03T00:00:00+00:00",
});

const FIELDS = [
  "five_hour_pct",
  "five_hour_reset",
  "seven_day_pct",
  "seven_day_reset",
  "updated_at",
  "stale",
  "age_min",
];

console.log(`릴레이 점검 — ${API}\n`);

// 1. 올리기
{
  const r = await post(sample(7));
  const body = await r.json();
  ok(r.status === 200 && body.ok === true, "올리면 {ok:true}", `${r.status} ${JSON.stringify(body)}`);
}

// 2. 바로 읽으면 일곱 필드가 그대로
{
  const r = await fetch(`${API}?key=${KEY}`);
  const body = await r.json();
  const names = Object.keys(body);

  ok(r.status === 200, "읽으면 200", String(r.status));
  ok(
    FIELDS.every((f) => names.includes(f)) && names.length === FIELDS.length,
    "일곱 필드가 그대로",
    names.join(", ")
  );
  ok(body.five_hour_pct === 7 && body.seven_day_pct === 55, "퍼센트는 0~100 숫자", `${body.five_hour_pct} / ${body.seven_day_pct}`);
  ok(body.five_hour_reset === "2026-07-31T22:19:59+00:00", "초기화 시각 원문 유지", String(body.five_hour_reset));
  ok(!Number.isNaN(Date.parse(body.updated_at)), "updated_at 은 ISO 8601", String(body.updated_at));
  ok(body.stale === false && body.age_min === 0, "방금 올린 값은 stale:false", `stale=${body.stale} age_min=${body.age_min}`);
  ok(r.headers.get("cache-control") === "no-store", "Cache-Control: no-store", String(r.headers.get("cache-control")));
}

// 3. 같은 키로 또 올리면 덮어쓴다 (행이 쌓이지 않는다)
{
  await post(sample(42));
  const body = await (await fetch(`${API}?key=${KEY}`)).json();
  ok(body.five_hour_pct === 42, "같은 키 재전송은 덮어쓰기", `five_hour_pct=${body.five_hour_pct}`);
}

// 4. 퍼센트는 0~100 으로 자른다
{
  await post({ ...sample(0), five_hour_pct: 999, seven_day_pct: -5 });
  const body = await (await fetch(`${API}?key=${KEY}`)).json();
  ok(body.five_hour_pct === 100 && body.seven_day_pct === 0, "0~100 밖은 잘린다", `${body.five_hour_pct} / ${body.seven_day_pct}`);
  await post(sample(7)); // 되돌려 놓기
}

// 5. 엉터리 키 → 400
{
  const g = await fetch(`${API}?key=abc`);
  const p = await post({ ...sample(7), key: "abc" });
  ok(g.status === 400, "엉터리 키로 읽으면 400", String(g.status));
  ok(p.status === 400, "엉터리 키로 올리면 400", String(p.status));
}

// 6. 없는 키 → 404
{
  const r = await fetch(`${API}?key=${GHOST}`);
  ok(r.status === 404, "기록 없는 키는 404", String(r.status));
}

// 7. 21분 전 값이면 stale:true — 저장소를 직접 건드린다
if (REST_URL && REST_TOKEN) {
  const slot = "cd:" + createHash("sha256").update(KEY).digest("hex");
  const old = {
    five_hour_pct: 7,
    five_hour_reset: "2026-07-31T22:19:59+00:00",
    seven_day_pct: 55,
    seven_day_reset: "2026-08-03T00:00:00+00:00",
    updated_at: new Date(Date.now() - 21 * 60000).toISOString(),
  };
  const w = await fetch(REST_URL, {
    method: "POST",
    headers: { Authorization: `Bearer ${REST_TOKEN}`, "Content-Type": "application/json" },
    body: JSON.stringify(["SET", slot, JSON.stringify(old), "EX", 600]),
  });
  if (!w.ok) {
    ok(false, "21분 전 값 심기", `저장소 응답 ${w.status}`);
  } else {
    const body = await (await fetch(`${API}?key=${KEY}`)).json();
    ok(body.stale === true && body.age_min === 21, "21분 전 값이면 stale:true", `stale=${body.stale} age_min=${body.age_min}`);
  }
  await post(sample(7)); // 되돌려 놓기
} else {
  console.log("  건너뜀  21분 전 값이면 stale:true  — UPSTASH_REDIS_REST_* 를 주면 확인한다");
}

console.log(failed ? `\n실패 ${failed}건` : "\n전부 통과");
process.exit(failed ? 1 : 0);
