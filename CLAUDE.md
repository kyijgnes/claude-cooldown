# CLAUDE.md

**클로드 쿨다운** — Claude 구독 한도(5시간 / 주간)를 바탕화면 위젯과
안드로이드 KWGT 위젯으로 보여주는 개인 도구. 친구들에게도 배포할 예정.

- repo: `claude-cooldown` / 엔드포인트: `/api/cooldown`
- 파이썬 모듈·파일은 `cooldown_` 접두사, 로컬 설정 파일은 `~/.claude_cooldown*.json`

## 구조

```
친구 PC (OAuth 토큰은 로컬에만 존재)
  └─ agent/cooldown_agent.py   5분마다 사용률 조회
        │  POST {key, 퍼센트 4개}
        ▼
  server/  Next.js API route → Supabase (service_role)
        ▲
        │  GET ?key=...
  폰 KWGT  $wg(url, json, .five_hour_pct)$
```

- `key` = 에이전트 첫 실행 시 생성되는 랜덤 32 hex. 읽기 비밀번호 역할.
- 데스크탑 위젯(`desktop/`)은 서버를 거치지 않고 로컬에서 직접 조회한다.

## 파일

| 경로 | 역할 |
|---|---|
| `desktop/cooldown_core.py` | **조회·파싱 공용 모듈. 파서는 여기 한 곳에만 둔다** |
| `desktop/cooldown_app.py` | **윈도우 앱 본체.** 바탕화면 위젯 + 트레이 아이콘 + 자동 실행 등록 |
| `agent/cooldown_agent.py` | 폰 위젯용 상주 에이전트. 조회 → 로컬 JSON 저장 → 서버 POST |
| `server/app/api/cooldown/route.ts` | POST(업서트) / GET(조회) 릴레이 |
| `server/schema.sql` | `public.claude_cooldown` 테이블, RLS on + 정책 없음 |
| `README.md` | 설치·배포 절차, KWGT 수식 |
| ~~`desktop/cooldown_overlay.py`~~ | 구버전. `cooldown_app.py` 로 대체됨 (삭제 예정) |
| ~~`desktop/cooldown_tray.py`~~ | 구버전. `cooldown_app.py` 로 대체됨 (삭제 예정) |

## 확정된 사실

- 사용량 조회: `GET https://api.anthropic.com/api/oauth/usage`
  - 헤더: `Authorization: Bearer <token>`, `anthropic-beta: oauth-2025-04-20`
  - 토큰 위치: `~/.claude/.credentials.json` → `claudeAiOauth.accessToken`
  - **공식 문서화되지 않은 엔드포인트.** 예고 없이 바뀔 수 있음.
    공식 API 요청 이슈: anthropics/claude-code#13585
- 폴링 간격 300초 고정. 더 짧으면 rate limit 에 걸린다.
- Claude Code 2.1.x 이상은 statusline 에 `rate_limits.five_hour` / `.seven_day` 를
  stdin 으로 넘겨준다. 네트워크 없이 쓰는 대안 경로 (statusline 용으로만 유효).
- KWGT 는 `$wg(url, json, .path)$` 로 JSON 파싱 가능. Flow 의 Time 트리거로
  주기 제어 가능. 둘 다 Pro 기능.

## 응답 형식 (2026-07-28 실측 확인)

```json
{"five_hour": {"utilization": 7.0, "resets_at": "2026-07-27T22:19:59+00:00"},
 "seven_day": {"utilization": 55.0, "resets_at": "..."},
 "seven_day_opus": null, "seven_day_sonnet": null,
 "limits": [{"kind": "weekly_scoped", "percent": 7,
             "scope": {"model": {"display_name": "Fable"}}}, ...],
 "extra_usage": {...}, "spend": {...}}
```

- `utilization` 은 **0~100 스케일**이다. 100 을 곱하지 말 것.
- 모델별 주간 한도는 `seven_day_opus` 같은 최상위 필드가 아니라 **`limits[]` 의
  `kind == "weekly_scoped"`** 에 들어온다. 최상위 필드는 이제 항상 null.
- 형식이 또 바뀌면 고칠 곳은 `desktop/cooldown_core.py` 한 곳뿐.
  확인은 `python desktop/cooldown_core.py` (원본 JSON 출력).

## 다음 작업

1. 구버전 `desktop/cooldown_overlay.py`, `desktop/cooldown_tray.py` 삭제
2. 서버 배포 (Supabase SQL 실행 → Vercel 환경변수 2개 → 배포)
3. 배포 패키징: PyInstaller onefile + `PUSH_URL` 을 빌드 시 주입
4. `limits[]` 의 `severity` 를 색상 임계값 대신 쓸지 검토 (지금은 50/80 자체 기준)
5. 폴더 2중 중첩(`13. 클로드 사용량/claude-cooldown/claude-cooldown/`) 정리,
   바깥 CLAUDE.md 중복 제거

## 하지 말 것

- `.credentials.json` 내용이나 accessToken 을 서버로 보내지 말 것. 퍼센트만 전송.
- `SUPABASE_SERVICE_ROLE_KEY` 를 클라이언트 번들이나 에이전트에 넣지 말 것.
- 폴링 간격을 300초 미만으로 낮추지 말 것.
- `claude_cooldown` 테이블에 RLS 정책을 추가하지 말 것 (anon 차단 상태가 의도된 설계).
