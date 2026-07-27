# CLAUDE.md

**클로드 쿨다운** — Claude 구독 한도(5시간 / 주간)를 바탕화면 위젯과
안드로이드 KWGT 위젯으로 보여주는 개인 도구. 친구들에게도 배포할 예정.

- repo: `claude-cooldown` / 엔드포인트: `/api/cooldown`
- 파이썬 모듈·파일은 `cooldown_` 접두사, 로컬 설정 파일은 `~/.claude_cooldown*.json`

## 구조

**윈도우 앱**(주력)은 서버를 거치지 않고 로컬에서 직접 조회한다.
**폰 위젯**은 서버 릴레이가 필요하다 — 아직 미배포.

```
내 PC (OAuth 토큰은 로컬에만 존재)
  ├─ windows/cooldown_app.py   바탕화면 위젯 + 트레이. 직접 조회, 서버 불필요
  └─ agent/cooldown_agent.py   5분마다 조회
        │  POST {key, 퍼센트 4개}
        ▼
  server/  Next.js API route → Supabase (service_role)
        ▲
        │  GET ?key=...
  폰 KWGT  $wg(url, json, .five_hour_pct)$
```

- `key` = 에이전트 첫 실행 시 생성되는 랜덤 32 hex. 읽기 비밀번호 역할.

## 파일

| 경로 | 역할 |
|---|---|
| `cooldown_core.py` | **조회·파싱 공용 모듈. 파서는 여기 한 곳에만 둔다** |
| `windows/cooldown_app.py` | **윈도우 앱 본체.** 창·트레이·조회·메뉴. 그리기는 안 한다 |
| `windows/skins/base.py` | 스킨이 지켜야 할 약속(Skin) + 공용 색·글꼴 |
| `windows/skins/{card,arc,table,slim}.py` | 디자인 4종. 우클릭 > 디자인 으로 전환 |
| `windows/_shot_skin.py` | 스킨을 4가지 상태로 렌더해 PNG 로 남기는 개발 도구 |
| `windows/클로드 쿨다운 실행.bat` | 콘솔 없이 앱을 띄우는 실행 파일 |
| `docs/디자인_요청서.md` | 디자이너에게 넘기는 브리프 + `docs/시안/` 참고 이미지 |
| `agent/cooldown_agent.py` | 폰 위젯용 상주 에이전트. 조회 → 로컬 JSON 저장 → 서버 POST |
| `server/app/api/cooldown/route.ts` | POST(업서트) / GET(조회) 릴레이 |
| `server/schema.sql` | `public.claude_cooldown` 테이블, RLS on + 정책 없음 |
| `requirements.txt` | requests / pillow / pystray / pywin32 |
| `README.md` | 설치·배포 절차, KWGT 수식 |

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
- 형식이 또 바뀌면 고칠 곳은 `cooldown_core.py` 한 곳뿐.
  확인은 `python cooldown_core.py` (원본 JSON 출력).

## 화면 규칙 (스킨을 만들거나 고칠 때)

- 새 스킨은 `base.Skin` 상속 + `skins/__init__.py` 의 `_MODULES` 에 한 줄 추가.
- **네 상태(정상/연결실패/재로그인/불러오는중)의 창 높이가 같아야 한다.**
  앱이 처음 잰 높이로 창을 고정하므로 늘어나면 잘린다. 오류는 자리를 새로
  만들지 말고 기존 자리의 색·글자를 바꿔서 표현한다.
- `show_error(text, keep_values, stamp)` 의 `keep_values` 가 참이면
  숫자·게이지를 건드리지 않는다 (일시적 연결 실패 — 마지막 값을 남긴다).
- 흐린 글자도 배경 대비 **4.5:1 이상**. 위계는 밝기가 아니라 글자 크기로 준다.
- 게이지 칸 계산은 `int(pct * n / 100)` (내림). `round` 를 쓰면 99% 와 100% 가
  구별되지 않는다.
- 확인: `python -u windows/_shot_skin.py <키> {ok|net|err|max} out.png`
  (`max` 는 100% · 가장 긴 문자열 · 긴 모델명인 최악 케이스)

## 작업표시줄에 붙이기

- 윈도우 11 은 작업표시줄 **안에** 넣는 길(데스크밴드)을 없앴다. 위에 겹쳐 놓는다.
- `dockable = True` 인 스킨에서만 쓸 수 있다 (지금은 `slim` 뿐).
  작업표시줄 높이에 맞춰 그리지 않는 스킨이 붙으면 삐져나오기 때문.
  다른 스킨으로 바꾸면 자동으로 풀리고 메뉴 항목이 잠긴다.
- 스킨 높이는 `base.taskbar_height()` 실측값에 맞춘다 — 고정 픽셀로 쓰지 말 것
  (작은 작업표시줄 40px, 고배율 60px+ 로 달라진다).
- **작업표시줄도 '항상 위' 라서 그냥 topmost 로 두면 가려진다.** 조작할 때마다
  스스로를 올리므로 `raise_above_taskbar()` 를 1.5초마다 다시 부른다.

## 다음 작업

1. **작업표시줄용 슬림 바 다듬기** — 크기는 맞았고 보기 좋게가 남았다.
   요청서는 `docs/디자인_요청서.md`
2. 배포 패키징: PyInstaller onefile (윈도우 앱)
2. 서버 배포 (Supabase SQL 실행 → Vercel 환경변수 2개 → 배포)
3. `limits[]` 의 `severity` 를 색상 임계값 대신 쓸지 검토 (지금은 50/80 자체 기준)

## 하지 말 것

- `.credentials.json` 내용이나 accessToken 을 서버로 보내지 말 것. 퍼센트만 전송.
- `SUPABASE_SERVICE_ROLE_KEY` 를 클라이언트 번들이나 에이전트에 넣지 말 것.
- 폴링 간격을 300초 미만으로 낮추지 말 것.
- `claude_cooldown` 테이블에 RLS 정책을 추가하지 말 것 (anon 차단 상태가 의도된 설계).
