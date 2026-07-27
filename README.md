# 클로드 쿨다운

Claude 구독 한도(5시간 / 주간)를 **윈도우 바탕화면 위젯 + 시작표시줄 아이콘**으로,
그리고 **안드로이드 KWGT 위젯**으로 보여주는 도구.

---

# A. 윈도우 앱 (이것만으로 완결 — 서버 필요 없음)

```
pip install requests pillow pystray pywin32
pythonw desktop/cooldown_app.py
```

- **바탕화면 위젯** — 드래그로 이동, 위치 자동 저장. 우클릭으로 메뉴.
- **시작표시줄 아이콘** — 5시간 사용률이 숫자로 뜬다. 80% 넘으면 한 번 알림.
- 우클릭 → **윈도우 켤 때 자동 실행** 을 켜면 시작 프로그램에 등록된다.
- 5분마다 갱신하고, 값을 `~/.claude_cooldown.json` 에도 써둔다.

> 아이콘이 안 보이면 시작표시줄 `^`(숨겨진 아이콘) 안에 있다.
> 밖으로 끌어다 놓으면 계속 보인다 — 윈도우가 새 아이콘을 기본으로 숨긴다.

응답 원본을 보려면:

```
python desktop/cooldown_core.py
```

---

# B. 폰 위젯 (KWGT) — 서버가 필요한 경우만

## 1. 서버 (형님 한 번만)

1. Supabase → SQL Editor → `schema.sql` 실행
2. Next.js 프로젝트에 `route.ts` 를 `app/api/cooldown/route.ts` 로 복사
3. `npm i @supabase/supabase-js`
4. Vercel 환경변수 2개 등록 후 배포
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`  ← 서버 전용, 절대 노출 금지
5. 확인: `curl "https://내앱.vercel.app/api/cooldown?key=00000000000000000000000000000000"` → `not found` 나오면 정상

## 2. 에이전트 (각자 PC)

`cooldown_agent.py` 상단 `PUSH_URL` 을 배포 주소로 바꿔서 나눠주세요.

```
pip install requests
pythonw cooldown_agent.py     # 상주 실행
python  cooldown_agent.py --info   # 내 키 / 위젯 주소 / KWGT 수식 확인
```

- 첫 실행 시 `~/.claude_cooldown_agent.json` 에 개인 키(32자리)가 생성됩니다.
- `Win+R` → `shell:startup` 폴더에 바로가기를 넣으면 부팅 시 자동 실행.
- Claude Code 로그인이 되어 있어야 합니다 (`~/.claude/.credentials.json` 필요).

## 3. 폰 위젯 (KWGT)

텍스트 요소에 수식으로:

```
5H   $wg("https://내앱.vercel.app/api/cooldown?key=내키", json, .five_hour_pct)$%
WEEK $wg("https://내앱.vercel.app/api/cooldown?key=내키", json, .seven_day_pct)$%
```

진행바(Progress) 요소의 Level 에도 같은 수식을 넣으면 게이지가 됩니다.

갱신 주기를 제어하려면 Flow 탭 → Time 트리거 5분 → Request(GET) → Global 저장 →
`$wg(gv(cu), json, .five_hour_pct)$` 형태로 쓰는 쪽이 더 안정적입니다.

> `wg()` 와 Flow 는 KWGT Pro 기능입니다.

PC가 꺼져 있으면 값이 멈추므로, 응답의 `stale` 이 true 일 때 회색 처리하면 좋습니다.

## 4. 친구에게 배포할 때 꼭 알려줄 것

- **토큰은 각자 PC 밖으로 나가지 않습니다.** 서버로 가는 건 퍼센트 숫자 4개뿐입니다.
- 키는 곧 읽기 비밀번호입니다. 남에게 주지 마세요. (유출돼도 보이는 건 사용률뿐)
- 5분 간격을 줄이지 마세요. 너무 잦으면 오히려 rate limit 에 걸립니다.
- 이 방식은 Anthropic이 공식 문서화하지 않은 엔드포인트를 씁니다.
  바뀌면 **모두 동시에** 안 됩니다. 그때는 에이전트만 고쳐서 다시 배포하면 됩니다.
- 응답 형식이 바뀌면 고칠 곳은 `desktop/cooldown_core.py` **한 곳뿐**입니다.
  (위젯·트레이·에이전트가 전부 이 모듈을 import 합니다)
