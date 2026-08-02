# 클로드 쿨다운

내 Claude 사용량(5시간·주간 한도)을 **컴퓨터**와 **폰**에 띄워 주는 작은 도구예요.

## ⬇️ 다운로드

**[👉 여기서 최신 버전 받기 (Releases)](https://github.com/kyijgnes/claude-cooldown/releases/latest)**

| | 받을 파일 | 쓰는 법 |
|---|---|---|
| 💻 **컴퓨터 (Windows)** | `claude-cooldown-v0.9.exe` | 더블클릭하면 끝 |
| 📱 **폰 (갤럭시/안드로이드)** | `claude-cooldown-v0.9.apk` | 폰에 넣고 설치 |

> 두 파일 모두 위 **Releases** 페이지 맨 위(최신 버전)에 있어요.
> **Claude Code 에 로그인돼 있어야** 내 사용량이 보입니다.

---

## 💻 컴퓨터에서 쓰는 법

1. `claude-cooldown-v0.9.exe` 를 더블클릭하면 끝이에요.
2. 작업표시줄 오른쪽에 얇은 막대로 뜹니다 (귀여운 마스코트 '클로디'도 같이).
3. 막대를 **클릭하면 새로고침**, **끌면 옮기기**, **우클릭하면 설정**(디자인·밝기 등)이에요.

- 처음 켤 때 파란 경고창(SmartScreen)이 뜨면 → `추가 정보` → `실행` 을 누르세요.
- 게이지의 세로 눈금은 **'적정선'**(창이 흐른 만큼) — 채운 색이 눈금을 앞질렀으면 그만큼 빨리 쓰는 중이에요.

## 📱 폰(갤럭시)에서 쓰는 법

폰에는 이렇게 뜹니다 — **상태바에 숫자**, **잠금화면과 AOD**, **홈 위젯**, **전용 배경화면**.

1. 릴리스에서 받은 `claude-cooldown-*.apk` 를 폰에 넣고 설치해요
   (`출처를 알 수 없는 앱` 허용을 한 번 물어봅니다).
2. 컴퓨터 위젯을 **우클릭 > 폰에서 보기 > 폰 연결…** 하면 QR 이 떠요.
3. 폰 앱에서 **PC 화면 QR 찍기** 를 누르고 그 QR 을 찍으면 끝이에요.
4. 앱 안 `옵션` 에서 **홈 화면에 위젯 넣기** / **배경화면에 넣기** 를 고르면 돼요.

- 컴퓨터가 꺼져 있어도 **초기화 시각은 폰이 알아서 맞춰요.** 그동안 새로 쓴 양만
  못 따라올 뿐이고, 그럴 땐 화면 구석에 작은 점이 뜹니다.
- 상태바 칩과 AOD 표시는 **안드로이드 16(One UI 8) 이상**에서 됩니다.
  그 아래 버전은 상태바 아이콘과 잠금화면까지 보여요.
- 이 기능은 **컴퓨터 쪽 서버 설정이 끝나 있어야** 동작해요 (아래 개발용 참고).

---

## 📁 폴더 구조

| 폴더 | 내용 |
|---|---|
| `pc/` | 컴퓨터 앱(위젯·트레이·마스코트) + 조회·자동시작 로직 + exe 빌드 |
| `android/` | 폰 앱(상태바·홈 위젯·잠금화면·AOD·배경화면) |
| `server/` | 폰이 값을 받아 가는 릴레이 서버(Next.js, Vercel) |

## 🛠️ 직접 만들거나 고칠 때 (개발용)

- 컴퓨터 앱 실행: `pip install -r pc/requirements.txt` 후 `pythonw pc/windows/cooldown_app.py`
- 나눠줄 exe 만들기: `pip install pyinstaller` 후 `python pc/build_exe.py` → `pc/dist/클로드 쿨다운.exe`
  (더블클릭용 `pc/exe 빌드.bat` 도 있어요)
- 폰 앱 빌드: `android/build.ps1` (APK) / `android/build.ps1 install` (연결된 폰에 설치)
  / `android/build.ps1 test` (폰 없이 화면 그림만 PNG 로)
- 릴레이 서버: Upstash Redis 를 하나 만들고 `server/` 를 Vercel 에 올린 뒤,
  환경변수 `UPSTASH_REDIS_REST_URL` 과 `UPSTASH_REDIS_REST_TOKEN` 을 넣으세요
  (자세한 절차·확인·되돌리기는 `server/README.md`).
  그 주소를 컴퓨터 위젯의 `폰 연결…` 창에 붙여 넣으면 됩니다.
- 새 버전 배포: `android/app/build.gradle.kts` 의 `versionCode` 를 올리고 `git tag v0.N` → `git push origin v0.N`
  (GitHub Actions 가 서명된 APK 를 만들어 릴리스에 붙여요). exe 는 `pc/build_exe.py` 로 만들어 같은 릴리스에 올립니다.
