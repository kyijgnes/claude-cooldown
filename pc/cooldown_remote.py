"""
원격 대기 — `claude rc` 를 창 없이 띄워 두는 로직 (쿨다운 위젯에 통합)
=====================================================================
폰이나 claude.ai/code 에서 **이 PC 에 새 세션을 열려면** PC 쪽에서
`claude rc`(Remote Control)가 상주해 있어야 한다. 원래는 터미널을 하나
띄워 두고 거기서 돌리는 물건인데, 그러자고 검은 창을 하루 종일 켜 둘
까닭이 없어서 위젯이 대신 들고 있는다.

이 파일은 **순수 로직만** 담는다 (Tk·트레이 없음). 위젯 본체
(windows/cooldown_app.py)가 이 모듈을 불러 쓴다. 단독 확인:

    python cooldown_remote.py            # 지금 상태만 출력
    python cooldown_remote.py --start    # 켜 보고 10초 지켜본 뒤 끈다

핵심:
- ★★ **자식에서 `CLAUDE_CODE_OAUTH_TOKEN` 을 빼고 띄운다.** `claude setup-token`
  으로 만든 장기 토큰은 **추론 전용**이라 원격 제어 권한이 없고, 클로드는 저장된
  로그인보다 그 환경변수를 먼저 쓴다 — 그냥 띄우면 로그인이 멀쩡해도
  `requires a full-scope login token` 으로 튕긴다. 그 환경변수 자체는 예약 작업이
  밤에 죽지 말라고 일부러 등록해 둔 것이라 **지우면 안 되고**, 여기서 자식에게만 뺀다.
- `claude rc` 는 **폴더 하나에 붙는다** — 거기서 열린 세션만 폰에서 쓸 수 있다.
  기본은 바탕화면\코딩, 없으면 홈.
- 콘솔 없이(CREATE_NO_WINDOW) 돌려도 정상 등록된다(2026-08-13 실측:
  `bridge:init Registered` → `Created initial session` → 폴 루프까지 확인).
- `claude` 는 npm 전역 설치면 `.cmd` 배치라 **자식이 cmd.exe → node.exe 로 두 겹**이다.
  끌 때 부모만 죽이면 node 가 남으므로 `taskkill /T` 로 **가지째** 끝낸다.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime

import cooldown_push  # 릴레이 주소·키는 '폰으로 보내기' 설정을 그대로 쓴다
# claude 실행 파일 찾기·자식 환경변수는 한 곳(cooldown_ping)에만 둔다
from cooldown_ping import child_env, find_claude

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".claude_cooldown_remote.json")
LOG_PATH = os.path.join(os.path.expanduser("~"), ".claude_cooldown_remote.log")
# 앱이 죽어도 자식은 살아남는다. 다시 켰을 때 그 놈을 알아보려고 PID 를 적어 둔다.
PID_PATH = os.path.join(os.path.expanduser("~"), ".claude_cooldown_remote.pid")

# 띄운 뒤 이만큼 안에 죽으면 '뜨다 만 것' 으로 본다 (등록까지 3초쯤 걸린다)
SETTLE_SEC = 12

# 죽은 까닭 두 가지 — **다루는 법이 다르다.**
#   · ERR_EARLY   곧바로 죽음 = 애초에 못 붙는 상태(로그인·폴더 신뢰). 되풀이해도 소용없다.
#   · ERR_DROPPED 한참 잘 돌다 끊김 = 밖에서 죽인 것. **그냥 다시 띄우면 된다.**
# 이걸 안 가르면 밖에서 세 번 죽었을 때 원격 대기가 스스로 꺼져 버린다 — 2026-08-14 에
# 업데이트 자동 적용이 5분마다 `claude.exe` 를 싹 죽이는 바람에 실제로 그렇게 꺼졌고,
# 그날 아침 내내 폰에서 이 PC 에 세션을 열 수 없었다.
ERR_EARLY = "붙지 못함 (로그인·폴더 신뢰 확인)"
ERR_DROPPED = "끊김"
NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW — 콘솔 없는 앱이라 검은 창이 뜨면 안 된다

DEFAULTS = {
    "enabled": False,   # 켜져 있어야 하나. 앱이 뜰 때 이 값대로 되살린다.
    "folder": "",       # 어느 폴더에서 돌 것인가. 비면 default_folder()
    "last_error": "",   # 마지막 실패 까닭 (화면 표시용)
    # 폰이 마지막으로 '이렇게 해 달라' 고 적은 시각. 같은 것을 두 번 따르지 않으려고 적어 둔다 —
    # 이게 없으면 사흘 전 폰에서 켠 것이 PC 에서 끌 때마다 되살아난다.
    "last_want_at": "",
}


# ---------------------------------------------------------------- 설정


def default_folder() -> str:
    """기본 작업 폴더. 바탕화면\\코딩 이 있으면 거기, 없으면 홈."""
    home = os.path.expanduser("~")
    cand = os.path.join(home, "Desktop", "코딩")
    return cand if os.path.isdir(cand) else home


def load_cfg() -> dict:
    cfg = dict(DEFAULTS)
    try:
        # utf-8-sig — 손으로 고치다 BOM 이 붙으면 json 이 통째로 못 읽고 기본값(꺼짐)으로
        # 떨어진다. 오류도 안 나서 '켰는데 안 켜진다' 로만 보인다(만들면서 실제로 겪었다).
        with open(CONFIG_PATH, encoding="utf-8-sig") as f:
            data = json.load(f)
        if isinstance(data, dict):
            cfg.update(data)
    except (OSError, ValueError):
        pass
    if not os.path.isdir(str(cfg.get("folder") or "")):
        cfg["folder"] = default_folder()
    return cfg


def save_cfg(cfg: dict) -> None:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False)
    except OSError:
        pass


def _log(line: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        old = []
        if os.path.exists(LOG_PATH):
            with open(LOG_PATH, encoding="utf-8") as f:
                old = f.read().splitlines()[-200:]
        old.append(f"[{stamp}] {line}")
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(old) + "\n")
    except OSError:
        pass


def friendly_error(raw) -> str:
    """실패 까닭을 화면에 보일 한국어 명사형으로. 원문은 로그에만 남긴다."""
    s = str(raw or "")
    low = s.lower()
    if "claude" in low and ("없" in s or "찾" in s or "not found" in low):
        return "클로드 코드가 없어요 (설치·로그인 확인)"
    if "full-scope" in low or "inference-only" in low:
        return "로그인이 필요해요 (claude auth login)"
    if "subscription" in low or "logged in" in low:
        return "클로드 로그인 필요"
    if "trust" in low:
        return "폴더 신뢰 필요 (그 폴더에서 claude 한 번 실행)"
    if "폴더" in s:
        return s
    return "실행 실패 (잠시 후 다시)"


# ---------------------------------------------------------------- 남은 프로세스


def _alive(pid: int) -> bool:
    """그 PID 가 아직 살아 있나. 윈도우 API 로만 본다(프로세스를 새로 띄우지 않는다)."""
    if not pid:
        return False
    try:
        import ctypes

        SYNCHRONIZE = 0x00100000
        h = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, int(pid))
        if not h:
            return False
        ctypes.windll.kernel32.CloseHandle(h)
        return True
    except Exception:  # noqa: BLE001 — 윈도우가 아니거나 권한이 없으면 모른다고 본다
        return False


def _read_pid() -> int:
    try:
        with open(PID_PATH, encoding="utf-8") as f:
            return int((f.read() or "0").strip())
    except (OSError, ValueError):
        return 0


def _write_pid(pid: int) -> None:
    try:
        if pid:
            with open(PID_PATH, "w", encoding="utf-8") as f:
                f.write(str(pid))
        elif os.path.exists(PID_PATH):
            os.remove(PID_PATH)
    except OSError:
        pass


def _kill_tree(pid: int) -> None:
    """가지째 끝낸다. claude 는 .cmd 라 cmd.exe → node.exe 로 두 겹이고,
    부모만 죽이면 node 가 남아 원격 대기가 계속 도는 것처럼 보인다."""
    if not pid:
        return
    try:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            timeout=15,
            creationflags=NO_WINDOW,
        )
    except Exception as e:  # noqa: BLE001
        _log(f"끄기 실패: {e}")


# ---------------------------------------------------------------- 본체


class Remote:
    """`claude rc` 하나를 쥐고 켜고 끈다. 상태를 들고 있으므로 앱에 하나만 둔다."""

    def __init__(self) -> None:
        self._p: subprocess.Popen | None = None
        self._pid = 0          # 우리가 띄운(또는 이어받은) 프로세스
        self._since: datetime | None = None
        self.last_error = ""

    # -------------------------------------------------- 상태

    def running(self) -> bool:
        if self._p is not None:
            return self._p.poll() is None
        return bool(self._pid) and _alive(self._pid)

    def adopt(self) -> bool:
        """앱이 다시 떠났을 때, 지난번에 띄워 둔 놈이 아직 살아 있으면 이어받는다.
        (앱이 죽어도 자식은 남으므로, 모르고 또 띄우면 둘이 겹친다)"""
        pid = _read_pid()
        if pid and _alive(pid):
            self._pid = pid
            self._since = None  # 언제부터인지는 모른다
            _log(f"이어받음: pid={pid}")
            return True
        _write_pid(0)
        return False

    def since(self) -> datetime | None:
        return self._since

    # -------------------------------------------------- 켜기 · 끄기

    def start(self, folder: str) -> tuple[bool, str]:
        """원격 대기를 켠다. (성공?, 짧은 결과 문구). 블로킹은 아니지만
        띄우고 나서 실제로 붙었는지는 `settled()` 가 나중에 판정한다."""
        if self.running():
            return True, "이미 켜져 있음"

        claude = find_claude()
        if not claude:
            self.last_error = "claude 없음"
            _log("실패: claude 실행 파일을 찾지 못함")
            return False, self.last_error

        folder = folder or default_folder()
        if not os.path.isdir(folder):
            self.last_error = "폴더 없음"
            _log(f"실패: 폴더 없음 {folder}")
            return False, self.last_error

        # ★ 장기 토큰을 자식에게만 뺀다 (맨 위 설명 참고). 지우는 게 아니다.
        env = child_env()

        try:
            p = subprocess.Popen(
                [claude, "rc"],
                cwd=folder,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=NO_WINDOW,
            )
        except Exception as e:  # noqa: BLE001
            self.last_error = str(e)[:80]
            _log(f"실패: {e}")
            return False, self.last_error

        self._p = p
        self._pid = p.pid
        self._since = datetime.now()
        self.last_error = ""
        _write_pid(p.pid)
        _log(f"켬: pid={p.pid} 폴더={folder}")
        return True, "켜짐"

    def stop(self) -> None:
        pid = self._pid or _read_pid()
        if pid:
            _kill_tree(pid)
            _log(f"끔: pid={pid}")
        self._p = None
        self._pid = 0
        self._since = None
        _write_pid(0)

    # -------------------------------------------------- 지켜보기

    def settled(self) -> bool:
        """띄운 지 SETTLE_SEC 이 지났나. 그 전에 죽으면 '뜨다 만 것' 으로 본다."""
        if self._since is None:
            return True  # 이어받은 놈은 이미 자리 잡은 것
        return (datetime.now() - self._since).total_seconds() >= SETTLE_SEC

    def died(self) -> str | None:
        """켜져 있어야 하는데 죽었으면 까닭을, 아니면 None.
        앱이 주기적으로 물어 보고 다시 살린다."""
        if self.running():
            return None
        if self._p is None and not self._pid:
            return None  # 애초에 안 켰다
        code = self._p.poll() if self._p is not None else None
        early = not self.settled()
        self._p = None
        self._pid = 0
        _write_pid(0)
        # 곧바로 죽었다 = 붙지 못한 것(로그인·신뢰 문제일 때가 많다).
        # 한참 돌다 죽었다 = 밖에서 죽인 것 — 다시 띄우면 된다.
        self.last_error = ERR_EARLY if early else ERR_DROPPED
        _log(f"죽음: 코드={code} {self.last_error}")
        return self.last_error


# ---------------------------------------------------------------- 폰에서 켜고 끄기
#
# 폰이 릴레이에 '원하는 상태(want)' 를 적어 두면 PC 가 주기적으로 읽어 따라간다.
# 반대로 PC 는 '지금 상태(state)' 를 적어 폰이 화면에 표시할 수 있게 한다.
# 주소·키는 **'폰으로 보내기'(cooldown_push) 설정을 그대로 쓴다** — 이미 QR 로 짝지어
# 놓은 것을 또 짝지을 까닭이 없다.
#
# ★★ **폴링 주기를 함부로 줄이지 말 것.** Upstash 무료는 월 50만 명령이고 사용량
#   중계만으로 이미 29%(20명 기준)를 쓴다. 여기 GET 은 MGET 하나(=명령 1)지만
#   주기가 곧 비용이라, 60초로 하면 20명 기준 한도를 넘긴다. 계산은 server/README.md.

REMOTE_PATH = "/api/remote"  # server/app/api/remote/route.ts 와 같아야 한다
NET_TIMEOUT = 12


def relay_ready(push_cfg: dict) -> bool:
    """폰과 짝지어져 있나. 안 짝지어져 있으면 폴링을 아예 안 한다(남의 무료 한도를 안 쓴다)."""
    return bool(cooldown_push.normalize_url(push_cfg.get("url"))) and bool(push_cfg.get("key"))


def _endpoint(push_cfg: dict) -> str:
    base = cooldown_push.normalize_url(push_cfg.get("url"))
    return base + REMOTE_PATH if base else ""


def want_of(data) -> tuple[str, str] | None:
    """응답에서 (원하는 상태, 적힌 시각)만 골라낸다. 형식이 아니면 None.

    사용량을 올린 응답(`/api/cooldown` POST)에도, 따로 물어본 응답(`/api/remote` GET)에도
    같은 두 필드가 들어 있어 **읽는 자리는 하나로 둔다.**
    """
    if not isinstance(data, dict):
        return None
    want, at = data.get("want"), data.get("want_at")
    if want in ("on", "off") and isinstance(at, str):
        return want, at
    return None


def fetch_want(push_cfg: dict) -> tuple[str, str] | None:
    """릴레이에서 (원하는 상태, 적힌 시각) 을 읽는다. 없거나 못 읽으면 None.
    네트워크를 타므로 **별도 스레드에서** 부를 것."""
    url = _endpoint(push_cfg)
    if not url:
        return None
    try:
        import requests

        r = requests.get(url, params={"key": push_cfg["key"]}, timeout=NET_TIMEOUT)
        if r.status_code != 200:
            return None
        data = r.json()
    except Exception:  # noqa: BLE001 — 못 읽으면 그냥 지금 상태를 지킨다
        return None
    return want_of(data)


def publish_state(push_cfg: dict, state: str) -> None:
    """지금 상태를 릴레이에 적는다(폰 화면 표시용). 실패해도 조용히 넘어간다 —
    이건 알림이지 기능이 아니다."""
    url = _endpoint(push_cfg)
    if not url or state not in ("on", "off", "fail"):
        return
    try:
        import requests

        requests.post(
            url, json={"key": push_cfg["key"], "state": state}, timeout=NET_TIMEOUT
        )
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------- 단독 확인


def _main(argv: list[str]) -> int:
    cfg = load_cfg()
    print("폴더    :", cfg["folder"])
    print("claude  :", find_claude() or "(못 찾음)")
    pid = _read_pid()
    print("적힌 PID:", pid or "(없음)", "· 살아있나:", _alive(pid) if pid else False)

    if "--start" not in argv:
        return 0

    import time

    r = Remote()
    ok, msg = r.start(cfg["folder"])
    print("켜기:", ok, msg)
    if not ok:
        return 1
    for _ in range(10):
        time.sleep(1)
        if not r.running():
            print("죽음:", r.died())
            return 1
    print("10초 동안 살아 있음 — 정상. 끄는 중")
    r.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
