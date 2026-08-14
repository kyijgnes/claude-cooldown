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

단독 확인:
    python cooldown_login.py            상태만 보기
    python cooldown_login.py --revive   사용량 안 쓰는 되살리기 한 번
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

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


def open_login_console() -> bool:
    """`claude auth login` 을 **보이는 콘솔 창**에서 시작한다.

    로그인 자체는 브라우저에서 사람이 한다 — 위젯은 창만 열어 준다
    (자격 증명을 대신 넣지 않는다).
    """
    claude = find_claude()
    if not claude:
        return False
    try:
        subprocess.Popen(
            f'start "클로드 코드 로그인" cmd /k "{claude}" auth login',
            shell=True,
            env=child_env(),  # ★ 장기 토큰이 물려 가면 로그인해도 그쪽이 이긴다
        )
        return True
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------- 단독 실행

if __name__ == "__main__":
    exp = cooldown_core.token_expiry()
    print(f"토큰 만료: {exp.astimezone():%Y-%m-%d %H:%M} " if exp else "토큰 만료: 모름 ")
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
