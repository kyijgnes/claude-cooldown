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

## 색 (밝게 / 어둡게)

- 색은 `skins/base.py` 에 **두 벌**(`DARK`, `LIGHT`) 있고, 지금 쓰는 한 벌이 `P` 다.
- 스킨은 **반드시 `from .base import P` 로 객체째 받아 `P.bg` 처럼 쓴다.**
  `from .base import BG` 처럼 값을 직접 가져오면 그 시점 색이 굳어 테마가 안 바뀐다.
  테마 전환은 `P` 의 값만 덮어쓰므로, 객체로 받아 둔 쪽은 자동으로 따라온다.
- 색은 만들 때 위젯에 박히므로, 전환하려면 **다시 그려야 한다**
  (`App._apply_theme` 가 `_build_body` → `_replay` 를 부른다).
- `theme` 설정은 `auto` / `light` / `dark`. `auto` 면 윈도우의 `AppsUseLightTheme`
  를 4초마다 확인해 따라간다.
- 새 색을 넣을 때는 **두 벌 다** 채우고 배경 대비 4.5:1 을 지킬 것.

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

## 동작 규칙 (건드릴 때 주의)

- **중복 실행 금지** — 이름 있는 뮤텍스로 판정. 두 번째 프로세스는 창을 띄우지 않고
  `~/.claude_cooldown.summon` 파일만 남기고 끝난다. 떠 있는 쪽이 `_pump` 에서
  그 파일을 보고 앞으로 나온다. (시작 프로그램·바로가기·.bat 이 겹쳐 눌리기 쉽다)
- **재시도 간격** — 폴링은 300초 고정이지만, `ConnectionFailed`(서버에 닿지도
  못함)일 때만 20 → 40 → 80 → 160 → 300 초로 빨리 되묻는다. 요청이 서버에
  도달하지 않았으므로 rate limit 과 무관하다. **429·로그인 만료·정상은 300초를 지킨다.**
- 한도 알림은 5시간·주간을 따로 센다(`self.warned` 딕셔너리). 주간이 차면 며칠을
  묶이므로 이쪽이 더 아프다.
- 창 위치는 저장·복원할 때 `clamp_to_screen()` 을 통과시킨다. 제목표시줄이 없어
  화면 밖으로 나가면 끌어올 수가 없다. 기준은 화면 전체가 아니라 **작업 영역**이다
  (전체 기준이면 작업표시줄에 덮여 12px 만 남는다).
- **`_release` 는 실제로 움직였을 때만 위치를 저장하고 붙이기를 푼다**(`DRAG_SLOP`).
  안 그러면 붙여 둔 위젯을 한 번 클릭했을 뿐인데 작업표시줄 뒤로 내려간다.
- **붙어 있는 동안에는 x/y 를 저장하지 않는다**(`_remember_spot`). 작업표시줄
  좌표가 자유 위치를 덮으면 나중에 풀었을 때 화면 끝에 걸린다.
- **`_pump` 은 try/finally 로 감싸 무슨 일이 있어도 다시 예약한다.** 여기서
  예외가 새면 갱신도 멈추고 트레이의 '종료' 마저 안 먹는다(같은 큐를 쓴다).
- 오류 문구는 `cooldown_core` 가 **짧은 명사형**으로 던진다. 슬림 바의 오류 자리가
  91px 뿐이라 길면 잘린다. 새 문구를 만들 때 폭을 재 볼 것.
- 응답 필드 이름만 바뀌어도 예외가 안 나고 값만 전부 None 이 된다. `parse` 가
  이걸 잡아 '형식 변경' 으로 올린다 — 안 잡으면 화면에 '--' 만 뜨고 고장난 줄 모른다.
- 오류가 나도 **마지막 값은 남긴다**(`keep_values`). 토큰이 8시간마다 만료돼
  자고 일어나면 매번 걸리는데, 그때마다 지우면 정작 궁금한 걸 못 본다.
  값이 언제 것인지는 기준 시각이 보여 준다 — 스킨은 오류 상태에서
  **실패한 시각이 아니라 마지막 성공 시각**을 써야 한다.

## 작업표시줄에 붙이기

- 윈도우 11 은 작업표시줄 **안에** 넣는 길(데스크밴드)을 없앴다. 위에 겹쳐 놓는다.
- `dockable = True` 인 스킨에서만 쓸 수 있다 (지금은 `slim` 뿐).
  작업표시줄 높이에 맞춰 그리지 않는 스킨이 붙으면 삐져나오기 때문.
  다른 스킨으로 바꾸면 자동으로 풀리고 메뉴 항목이 잠긴다.
- 스킨 높이는 `base.taskbar_height()` 실측값에 맞춘다 — 고정 픽셀로 쓰지 말 것
  (작은 작업표시줄 40px, 고배율 60px+ 로 달라진다).
- **작업표시줄도 '항상 위' 라서 그냥 topmost 로 두면 가려진다.** 조작할 때마다
  스스로를 올리므로 `raise_above_taskbar()` 를 1.5초마다 다시 부른다.

## exe 로 묶을 때 (build_exe.py)

- `skins/__init__.py` 가 `importlib` 로 스킨을 불러오므로 PyInstaller 가 스스로
  못 찾는다. **`--hidden-import skins.card` 처럼 스킨마다 넣어야 한다.**
  빼먹으면 exe 에 디자인이 하나도 안 들어간다.
- `cooldown_core.py` 가 저장소 루트에 있어 `--paths` 로 루트와 `windows` 를 둘 다 준다.
- 자동 실행 바로가기는 `launch_command()` 가 판단한다 — 묶인 상태(`sys.frozen`)면
  exe 자신을, 아니면 pythonw + 스크립트를 등록한다. 옮겨도 시작할 때 스스로 고친다.
- 서명이 없어 처음 실행할 때 SmartScreen 이 막는다. 정상이며 `추가 정보 > 실행`.

## 다음 작업

1. **작업표시줄용 슬림 바 다듬기** — 크기는 맞았고 보기 좋게가 남았다.
   요청서는 `docs/디자인_요청서.md`
2. 폰 위젯 서버 배포 (Supabase + Vercel)
2. 서버 배포 (Supabase SQL 실행 → Vercel 환경변수 2개 → 배포)
3. `limits[]` 의 `severity` 를 색상 임계값 대신 쓸지 검토 (지금은 50/80 자체 기준)

## 하지 말 것

- `.credentials.json` 내용이나 accessToken 을 서버로 보내지 말 것. 퍼센트만 전송.
- `SUPABASE_SERVICE_ROLE_KEY` 를 클라이언트 번들이나 에이전트에 넣지 말 것.
- 폴링 간격을 300초 미만으로 낮추지 말 것.
- `claude_cooldown` 테이블에 RLS 정책을 추가하지 말 것 (anon 차단 상태가 의도된 설계).
