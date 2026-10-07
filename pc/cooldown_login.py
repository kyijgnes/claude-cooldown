"""
클로드 쿨다운 — 로그인 상태 확인·잇기 (순수 로직, Tk 없음)
============================================================
위젯은 `~/.claude/.credentials.json` 의 accessToken 으로 사용량을 직접 조회한다.
그 토큰은 **발급 8시간 뒤에 만료**되고, 새로 발급할 수 있는 건 클로드 코드 CLI 뿐이다 —
그래서 클로드 코드를 8시간 넘게 안 쓰면(자고 일어나면) **로그인은 멀쩡한데 위젯만 멎는다.**
이 파일이 그 상태를 알아보고 되살린다.

되살리기는 **사다리**다. 싼 것부터 밟고, 토큰이 새로 발급되면 곧바로 멈춘다:

  1) `FREE_STEPS` — 사용량을 한 톨도 안 쓰는 CLI 명령. CLI 가 API 를 부르는 김에
     토큰을 스스로 새로 발급해 파일에 써 준다. **한도가 안 깎이고 5시간 창도 안 열린다.**
  2) 그래도 안 되면 `claude -p` 핑(`cooldown_ping.send_ping`) — 확실하지만
     **5시간 창이 닫혀 있었다면 그 순간 열린다.** 그래서 창이 이미 열려 있을 때만
     자동으로 밟고, 닫혀 있으면 사용자에게 한 번 묻는다 (판단은 위젯 쪽).

★★ **위젯이 토큰을 직접 재발급하지 않는다.** OAuth 재발급은 리프레시 토큰까지
   회전시킨다(2026-08-05 실측 확인: 재발급 뒤 refreshTokenExpiresAt 이 바뀐다).
   위젯이 `.credentials.json` 을 덮어쓰다 CLI 와 엇갈리면 **진짜로 로그인이 풀린다.**
   발급은 언제나 CLI 에게만 시킨다 — 이 규칙을 되돌리지 말 것.

★★ **되살리기가 안 먹던 까닭**(2026-08-14): CLI 를 부를 때 환경변수
   `CLAUDE_CODE_OAUTH_TOKEN`(장기 토큰)이 그대로 물려 가면, CLI 는 저장된 로그인
   대신 그 토큰으로 인증하고 **`.credentials.json` 을 건드리지 않는다.** 계단이
   전부 '성공' 하는데 토큰은 여전히 낡아, 컴퓨터를 켤 때마다 위젯이 `눌러서 로그인
   잇기` 에 멎어 있었다. 그래서 자식에게는 늘 `cooldown_ping.child_env()` 를 준다 —
   까닭·실측은 그 함수 주석에.

**로그인 자체도 한 달이면 끝난다**(`expiry`). 위의 되살리기는 리프레시 토큰이 살아 있어야
되는 일이고, 그 리프레시 토큰은 `refreshTokenExpiresAt`(발급 약 27~30일 뒤)에 **절대 만료**된다.
원격 대기가 쉬지 않고 돌아도 늘어나지 않는다. 그 순간 CLI 가 자격 파일의 토큰을 빈 값으로
지우고 사람이 `claude auth login` 을 다시 해야 한다(2026-10-07 05:21 만료 → 09:34 지워짐,
폰 원격 세션에서 '다시 로그인해야 합니다' 를 보고서야 알았다). 그래서 3일 전부터 미리 알린다.

단독 확인:
    python cooldown_login.py            상태만 보기
    python cooldown_login.py --revive   사용량 안 쓰는 되살리기 한 번
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone

from cooldown_ping import child_env, find_claude
import cooldown_core

STATUS_TIMEOUT = 25  # `claude auth status` 는 로컬 확인이라 금방 끝난다 (초)
STEP_TIMEOUT = 90  # 되살리기 한 계단 (초). MCP 상태 확인이 붙어 있어 넉넉히 준다.

# 사용량(한도)을 안 쓰면서 CLI 에게 토큰을 새로 발급하게 만드는 명령들.
# CLI 는 API 를 부르기 직전에 만료된 토큰을 스스로 갱신하므로, '조회는 하지만
# 추론은 안 하는' 명령이면 공짜로 토큰만 새로 얻는다.
#   · mcp list      — 2026-08-05 이 PC 에서 실제로 갱신된 것을 확인한 계단
#   · agents --json — 가볍고 무해한 예비 계단 (앞이 안 먹는 환경 대비)
# 새 계단을 찾으면 여기에 한 줄 더한다. 판정은 늘 '토큰이 새로 발급됐나' 하나뿐이라,
# 계단이 아무 효과가 없어도 잘못될 일은 없다.
FREE_STEPS: list[list[str]] = [
    ["mcp", "list"],
    ["agents", "--json"],
]

# 상태값 — 화면은 이 다섯 가지만 안다
OK = "ok"  # 토큰이 살아 있다. 조회된다.
STALE = "stale"  # 로그인은 살아 있는데 토큰만 낡았다 → 되살리면 된다
LOGGED_OUT = "logged_out"  # 진짜로 로그아웃됐다 → 사람이 다시 로그인해야 한다
NO_CLI = "no_cli"  # 클로드 코드가 이 PC 에 없다 → 되살릴 방법이 없다
UNKNOWN = "unknown"

# 로그인이 끝나는 날 며칠 전부터 알릴지. **달력 날짜로 센다** — 11/03 23:11 에 끝나면
# 10/31 하루 내내 D-3 이다(시각으로 세면 같은 날 안에서 D-3 이 D-2 로 바뀐다).
WARN_DAYS = 3
# 가짜 자격 파일 자리(시험용). 이 환경변수가 있으면 **로그인 만료 판정만** 그 파일을 읽는다 —
# 사용량 조회·되살리기는 진짜 파일 그대로라, 가짜 토큰이 서버로 나갈 일이 없다.
FAKE_ENV = "COOLDOWN_FAKE_LOGIN"


@dataclass(frozen=True)
class Expiry:
    """클로드 코드 로그인(리프레시 토큰)이 언제 끝나나. 토큰 원문은 담지 않는다."""

    at: datetime | None  # 끝나는 시각 (UTC aware). 자격 파일에 없으면 None
    gone: bool  # 이미 끝났다 — 사람이 다시 로그인해야 한다
    days: int | None  # 끝나는 날까지 남은 날수(달력). 모르거나 끝났으면 None

    @property
    def soon(self) -> bool:
        """WARN_DAYS 안쪽으로 다가왔다 (아직 안 끝남)."""
        return not self.gone and self.days is not None and self.days <= WARN_DAYS

    @property
    def short(self) -> str:
        """위젯 알림 자리에 얹는 한 마디. 알릴 것이 없으면 빈 문자열."""
        if self.gone:
            return "로그인 필요"
        if not self.soon:
            return ""
        return "로그인 만료 오늘" if self.days == 0 else f"로그인 만료 D-{self.days}"

    @property
    def when(self) -> str:
        """끝나는 시각 `11/03 23:11`. 모르면 빈 문자열."""
        return f"{self.at.astimezone():%m/%d %H:%M}" if self.at else ""


def cred_path() -> str:
    """로그인 만료 판정이 읽는 자격 파일. 시험할 때는 FAKE_ENV 가 가리키는 가짜."""
    return os.environ.get(FAKE_ENV) or cooldown_core.CRED_PATH


def expiry(now: datetime | None = None) -> Expiry | None:
    """자격 파일만 보고 로그인이 언제 끝나나 판정한다. **CLI 를 부르지 않는다**(1분마다 불러도 공짜).

    풀린 것으로 보는 셋(2026-10-07 실측: 갱신에 실패한 CLI 가 남긴 모양이 이렇다):
      · accessToken 이나 refreshToken 이 빈 값
      · expiresAt 이 0
      · refreshTokenExpiresAt 이 지났다(토큰은 아직 남아 있어도 다음 갱신에서 지워진다)
    파일이 없거나 못 읽으면(CLI 가 쓰는 중) None — 모를 때는 아무것도 띄우지 않는다.
    """
    try:
        with open(cred_path(), encoding="utf-8") as f:
            oauth = json.load(f).get("claudeAiOauth")
    except (OSError, ValueError, AttributeError):
        return None
    if not isinstance(oauth, dict):
        return None

    raw = oauth.get("refreshTokenExpiresAt")
    at = None
    if isinstance(raw, (int, float)) and raw > 0:
        try:
            at = datetime.fromtimestamp(raw / 1000, timezone.utc)
        except (ValueError, OSError, OverflowError):
            at = None

    now = now or datetime.now(timezone.utc)
    wiped = (
        not oauth.get("accessToken")
        or not oauth.get("refreshToken")
        or oauth.get("expiresAt") == 0
    )
    if wiped or (at is not None and now >= at):
        return Expiry(at, True, None)
    if at is None:  # 옛 CLI 라 끝나는 날을 안 적어 둔다 — 알릴 길이 없다
        return Expiry(None, False, None)
    days = (at.astimezone().date() - now.astimezone().date()).days
    return Expiry(at, False, days)


def _run(args: list[str], timeout: int) -> tuple[int, str]:
    """claude CLI 를 콘솔 창 없이 돌린다. (종료코드, 합친 출력)."""
    claude = find_claude()
    if not claude:
        return -1, "claude 없음"
    cmd = " ".join(['"' + claude.replace('"', '""') + '"'] + args)
    try:
        r = subprocess.run(
            cmd,
            shell=True,
            env=child_env(),  # ★ 장기 토큰을 뺀다 — 아래 '되살리기가 안 먹던 까닭'
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired:
        return -1, "시간 초과"
    except Exception as e:  # noqa: BLE001
        return -1, str(e)[:80]
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def auth_status() -> dict | None:
    """`claude auth status --json` 의 결과. CLI 가 없거나 읽을 수 없으면 None.

    로컬 확인이라 사용량을 쓰지 않고, 토큰도 새로 발급하지 않는다 —
    '진짜 로그아웃' 과 '토큰만 낡음' 을 가르는 용도로만 쓴다.
    """
    code, out = _run(["auth", "status", "--json"], STATUS_TIMEOUT)
    if code != 0:
        return None
    start = out.find("{")
    end = out.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(out[start : end + 1])
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def account(status: dict | None) -> str:
    """상태에서 뽑은 계정 표시 문자열. 모르면 빈 문자열."""
    if not status:
        return ""
    return str(status.get("email") or status.get("authMethod") or "")


def state(status: dict | None = None) -> str:
    """지금 로그인 상태 한 낱말. `status` 를 넘기면 CLI 를 다시 부르지 않는다.

    토큰이 살아 있으면 CLI 를 아예 안 부른다 — 멀쩡할 때 프로세스를 띄울 까닭이 없다.
    """
    stale = cooldown_core.token_stale()
    if stale is False:
        return OK
    if find_claude() is None:
        return NO_CLI
    if status is None:
        status = auth_status()
    if status is None:
        return UNKNOWN
    if not status.get("loggedIn"):
        return LOGGED_OUT
    return STALE


def revive_free() -> bool:
    """사용량을 안 쓰고 토큰을 되살려 본다. 새 토큰이 나왔으면 True.

    계단을 하나 밟을 때마다 `.credentials.json` 의 만료 시각을 다시 읽어,
    **새로 발급됐으면 거기서 멈춘다** (뒤 계단은 안 밟는다).
    """
    if find_claude() is None:
        return False
    for args in FREE_STEPS:
        _run(args, STEP_TIMEOUT)
        if cooldown_core.token_stale() is False:
            return True
    return False


def login_command() -> str:
    """사람이 직접 쳐야 하는 로그인 명령. 화면에 그대로 보여 준다."""
    return "claude auth login"


def login_cli() -> str | None:
    """다시 로그인에 쓸 CLI. **npm 전역 것을 먼저** 고른다 — 원격 대기·핑이 쓰는 것이 그것이다.
    (자격 파일은 어느 CLI 든 같은 `~/.claude/.credentials.json` 이라, 없으면 찾은 것으로 한다)"""
    npm = os.path.join(os.environ.get("APPDATA", ""), "npm", "claude.cmd")
    return npm if os.path.exists(npm) else find_claude()


def open_login_console() -> bool:
    """`claude auth login` 을 **보이는 파워셸 창**에서 시작한다.

    로그인 자체는 브라우저에서 사람이 한다 — 위젯은 창만 열어 준다
    (자격 증명을 대신 넣지 않는다). 승인 뒤 브라우저가 내준 코드를 이 창에 붙여 넣어야 끝난다.
    """
    claude = login_cli()
    if not claude:
        return False
    quoted = "'" + claude.replace("'", "''") + "'"
    script = f"$Host.UI.RawUI.WindowTitle = '클로드 코드 로그인'; & {quoted} auth login"
    try:
        subprocess.Popen(
            ["powershell", "-NoExit", "-NoProfile", "-Command", script],
            env=child_env(),  # ★ 장기 토큰이 물려 가면 로그인해도 그쪽이 이긴다
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        )
        return True
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------- 단독 실행

if __name__ == "__main__":
    exp = cooldown_core.token_expiry()
    print(f"토큰 만료: {exp.astimezone():%Y-%m-%d %H:%M} " if exp else "토큰 만료: 모름 ")
    login = expiry()
    if login is None:
        print("로그인 유지: 모름")
    else:
        left = "끝남" if login.gone else f"{login.days}일 남음" if login.days is not None else "날짜 없음"
        print(f"로그인 유지: {login.when or '-'} ({left}) · 위젯 알림: {login.short or '없음'}")
    st = state()
    print(f"상태: {st}")
    if st != OK:
        print(f"계정: {account(auth_status()) or '-'}")
    if "--revive" in sys.argv:
        print("되살리는 중… (사용량 안 씀)")
        print("결과:", "이어짐" if revive_free() else "실패 — 클로드 코드를 한 번 쓰세요")
        exp = cooldown_core.token_expiry()
        if exp:
            print(f"토큰 만료: {exp.astimezone():%Y-%m-%d %H:%M}")
    if not os.path.exists(cooldown_core.CRED_PATH):
        print("(자격 파일이 없습니다 — 클로드 코드에 로그인하세요)")
