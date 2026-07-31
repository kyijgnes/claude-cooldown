# 릴레이 서버 (server/)

PC 위젯이 올린 사용률을 폰 앱이 읽어가는 중계. **저장소는 Upstash Redis.**
(2026-07-31 에 Supabase 에서 옮겼다. 옛 `schema.sql` 자리를 이 문서가 대신한다.)

```
PC 위젯 ──POST /api/cooldown──▶ Vercel (이 폴더) ──▶ Upstash Redis
폰 앱  ──GET  /api/cooldown?key=…──▶
```

- 주소: `https://<내-릴레이>.vercel.app`
- 코드: `app/api/cooldown/route.ts` 한 파일. **의존성은 `next`·`react` 뿐이다**(저장소 SDK 없음).

## 무엇을 저장하나

사용자 한 명당 **한 줄**, 값 다섯 개뿐이다. 이름·계정·토큰은 들어오지 않는다.

| 필드 | 예시 |
|---|---|
| `five_hour_pct` / `seven_day_pct` | `7` / `55` (0~100) |
| `five_hour_reset` / `seven_day_reset` | `2026-07-31T22:19:59+00:00` |
| `updated_at` | 서버가 찍는다 |

- 저장 위치는 `cd:<key 의 SHA-256>` 이다 — **`key` 원문은 저장소에 남지 않는다.**
  `key` 는 읽기 비밀번호라, 저장소가 통째로 새더라도 남의 값을 읽을 수 없게 한 것.
  API 의 동작은 그대로다(폰은 `key` 만 알면 된다).
- 값마다 **14일 TTL** 이 붙는다. 그 사이 한 번도 안 올라오면 저절로 사라진다
  (Supabase 때는 이걸 하려면 주 1회 cron 이 필요했다. 이제 청소가 없다).

## 저장소 만들기 (한 번)

**Vercel 마켓플레이스로 붙인다** — 환경변수가 저절로 꽂히고 청구도 Vercel 한 곳으로 모인다.

1. Vercel > 이 프로젝트 > **Storage** > `Create Database` > **Upstash for Redis**
2. Plan **Free**, Region 은 폰·PC 와 가까운 곳(`ap-northeast-1` 도쿄)
3. 이 프로젝트에 **Connect** — 환경변수가 자동으로 들어온다
4. **Deployments > 맨 위 > Redeploy** (환경변수는 재배포해야 반영된다)

스키마·테이블·마이그레이션은 없다. **DB 하나 만들어 붙이는 게 세팅의 전부다.**

> 마켓플레이스가 꽂아 주는 이름은 `KV_REST_API_URL` / `KV_REST_API_TOKEN` 이고,
> [console.upstash.com](https://console.upstash.com) 에서 직접 만들면(신용카드 없이 된다)
> `UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN` 이다.
> `route.ts` 가 **두 이름을 다 받으므로** 어느 쪽으로 만들든 그대로 돈다.

## Vercel 환경변수

| 이름 | 값 | 어디서 |
|---|---|---|
| `KV_REST_API_URL`<br>(또는 `UPSTASH_REDIS_REST_URL`) | `https://xxx.upstash.io` | 마켓플레이스가 자동 · 직접 만들면 Upstash 콘솔 > REST API |
| `KV_REST_API_TOKEN`<br>(또는 `UPSTASH_REDIS_REST_TOKEN`) | 긴 토큰 | 〃 (**클라이언트에 노출 금지**) |

- 손으로 넣을 때는 **Production·Preview 둘 다**에 넣고 재배포한다.
- 옛 `NEXT_PUBLIC_SUPABASE_URL` · `SUPABASE_SERVICE_ROLE_KEY` 는 **지운다.**
- 둘 다 없으면 API 가 500 을 낸다(폰은 `PC 기록 없음` 대신 서버 오류를 본다).

## 배포

```bash
cd server && npm install && npx next build   # 로컬 확인
```

Vercel 은 이 저장소에 붙어 있어 `main` 에 밀면 자동 배포된다.

## 확인

```bash
node relay_check.mjs https://<내-릴레이>.vercel.app
```

올리기·되읽기·덮어쓰기·잘못된 키(400)·없는 키(404)·`no-store`·필드 이름 일곱 개를 한 번에 본다.
`UPSTASH_REDIS_REST_*` 를 함께 주면 **21분 전 값을 심어 `stale:true`** 까지 확인한다.

```bash
UPSTASH_REDIS_REST_URL=... UPSTASH_REDIS_REST_TOKEN=... node relay_check.mjs <주소>
```

저장소를 또 갈아치울 일이 생기면 **이 스크립트가 합격 기준**이다.

## 무료 한도 (사용자 20명 기준)

Upstash Free — **월 50만 명령**, 256MB, 월 10GB 전송.
요청 한 번이 명령 한 번이다(POST=`SET`, GET=`GET`).

| | 주기 | 한 사람 · 한 달 | 20명 |
|---|---|---|---|
| 쓰기 (PC→서버) | 5분마다 · 하루 12시간 | 4,320 | 86,400 |
| 읽기 (폰→서버) | 15분마다 | 2,880 | 57,600 |
| 합계 | | 7,200 | **144,000 (한도의 29%)** |

**약 69명까지 무료 한도 안이다.** 저장 용량은 한 줄이 200바이트 남짓이라 256MB 는 무의미하게 넉넉하다.
(무료 DB 는 **요청이 30일 넘게 하나도 없으면** 보관 처리된다 — PC 가 5분마다 올리므로 해당 없음.)

## 되돌리기 (Supabase 판으로)

이전 커밋의 `route.ts` 와 `schema.sql` 을 되살리면 된다. 데이터 이전은 필요 없다 —
**PC 위젯이 5분마다 다시 올리므로 5분이면 저절로 채워진다.**

```bash
git log --oneline -- server/app/api/cooldown/route.ts     # 이전 커밋 찾기
git checkout <커밋> -- server/app/api/cooldown/route.ts server/schema.sql
cd server && npm install @supabase/supabase-js
```

그리고 Supabase 프로젝트를 다시 만들어 `schema.sql` 을 실행한 뒤,
Vercel 환경변수를 `NEXT_PUBLIC_SUPABASE_URL` · `SUPABASE_SERVICE_ROLE_KEY` 로 되돌리고 재배포한다.
**주소·경로·응답 형식은 어느 쪽이든 같으므로 폰은 재페어링이 필요 없다.**

## 바꾸면 안 되는 것

친구들 폰에 이미 앱이 깔려 있고 주소와 키가 저장돼 있다. 아래가 바뀌면 **전원 재페어링**이다.

- 주소 `…vercel.app` · 경로 `/api/cooldown`
- 키 규칙 `^[0-9a-f]{32}$`
- GET 응답의 일곱 필드 이름과 타입, `Cache-Control: no-store`
- 400(키 오류) / 404(기록 없음) 구분 — 폰이 코드별로 다른 문구를 띄운다

`key` 는 로그·에러 메시지·모니터링에 남기지 않는다(읽기 비밀번호다).
