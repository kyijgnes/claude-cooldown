"""클로드 앱 업데이트 대기 감시 — Tk 없음.

**왜 있나.** 클로드 데스크톱은 MSIX 패키지라, 앱이 켜져 있는 동안 새 버전을 내려받으면
Windows 가 등록을 미룬다(`DeferRegistrationWhenPackagesAreInUse`). 미뤄둔 등록은 나중에
`ForceApplicationShutdownOption` 으로 적용되는데, 이때 **실행 중인 클로드를 전부 죽인다.**
진행 중이던 작업은 그대로 날아간다 — 2026-08-07 05:09 과 21:14 에 두 번 당했다.

대기 중인지 미리 알면 편할 때 껐다 켜서 피할 수 있다. 이 모듈은 그 판정만 한다.

**나중에 빼기.** 클로드 쪽이 작업 중인 세션을 죽이지 않게 고쳐지면 이 파일을 지우고
`cooldown_app.py` 에서 `cooldown_update` 를 쓰는 곳(주석 `[업데이트 대기]` 로 표시해 뒀다)만
지우면 끝난다. 다른 기능과 얽혀 있지 않다.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime

# 클로드 앱 식별자 — 실행·종료에 쓴다
APP_LINK = r"shell:AppsFolder\Claude_pzs8sxrjxfjjc!Claude"
IMAGE_NAME = "Claude.exe"

_NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW — 콘솔 없는 앱이라 창이 뜨면 안 된다


@dataclass(frozen=True)
class Pending:
    """등록을 기다리고 있는 업데이트."""

    current: str  # 지금 돌고 있는 버전
    target: str  # 등록을 기다리는 버전
    since: datetime | None  # 내려받은 시각 (모르면 None)

    @property
    def short(self) -> str:
        """위젯의 좁은 알림 자리에 얹을 문구. 명사형 한 줄."""
        return "업데이트 대기"

    @property
    def line(self) -> str:
        """트레이·메뉴에 쓸 한 줄. 값을 그대로 보여 준다."""
        return f"클로드 {self.current} → {self.target} 등록 대기"


def _run(args: list[str], timeout: float = 25.0) -> str:
    try:
        out = subprocess.run(
            args,
            capture_output=True,
            timeout=timeout,
            creationflags=_NO_WINDOW,
        )
    except Exception:  # noqa: BLE001  파워셸이 없거나 막혔을 때 — 조용히 포기한다
        return ""
    return out.stdout.decode("utf-8", "replace")


def _ps(script: str, timeout: float = 25.0) -> str:
    return _run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        timeout,
    )


def _ver(s: str) -> tuple[int, ...]:
    """'1.26832.0' 과 '1.26832.0.0' 이 같게 비교되도록 네 자리로 맞춘다."""
    parts = []
    for chunk in (s or "").split("."):
        try:
            parts.append(int(chunk))
        except ValueError:
            parts.append(0)
    return tuple((parts + [0, 0, 0, 0])[:4])


# 판정 재료를 한 번에 긁어 온다.
#   cur   지금 등록돼 있는(= 돌고 있는) 버전
#   vers  최근 '등록 지연' 경고(이벤트 658)에 적힌 버전들.
#         메시지에 구/신 버전이 둘 다 나오는데 **순서가 언어마다 다르다** — 그래서
#         순서를 믿지 않고 cur 보다 높은 것을 골라낸다.
#   when  그 경고가 찍힌 시각
#   seen  앱 업데이터가 마지막으로 본 버전 (이벤트 로그가 막혔을 때의 보조 신호)
_PROBE = r"""
$ErrorActionPreference = 'SilentlyContinue'
$cur = (Get-AppxPackage -Name Claude).Version
$vers = @(); $when = ''
$ev = Get-WinEvent -FilterHashtable @{
        LogName = 'Microsoft-Windows-AppXDeploymentServer/Operational'; Id = 658
      } -MaxEvents 40 | Where-Object { $_.Message -match 'Claude_' } | Select-Object -First 1
if ($ev) {
    $when = $ev.TimeCreated.ToString('yyyy-MM-ddTHH:mm:ss')
    $vers = @([regex]::Matches($ev.Message, 'Claude_([\d\.]+)_x64') |
              ForEach-Object { $_.Groups[1].Value })
}
$seen = ''
$cfg = Join-Path $env:APPDATA 'Claude\config.json'
if (Test-Path $cfg) {
    $seen = (Get-Content $cfg -Raw -Encoding UTF8 | ConvertFrom-Json).updaterLastSeenVersion
}
[pscustomobject]@{ cur = "$cur"; vers = @($vers); when = "$when"; seen = "$seen" } |
    ConvertTo-Json -Compress
"""


def check() -> Pending | None:
    """대기 중인 업데이트가 있으면 Pending, 없거나 알 수 없으면 None.

    알 수 없을 때도 None 이다 — 확실할 때만 경고한다. 없는 걱정을 띄우는 쪽이 더 나쁘다.
    """
    raw = _ps(_PROBE).strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None

    cur = (data.get("cur") or "").strip()
    if not cur:
        return None

    cands = data.get("vers") or []
    if isinstance(cands, str):  # 원소가 하나면 ConvertTo-Json 이 배열을 벗긴다
        cands = [cands]
    seen = (data.get("seen") or "").strip()
    if seen:
        cands = list(cands) + [seen]

    target = ""
    for v in cands:
        v = (v or "").strip()
        if _ver(v) > _ver(cur) and (not target or _ver(v) > _ver(target)):
            target = v
    if not target:
        return None

    since = None
    when = (data.get("when") or "").strip()
    if when:
        try:
            since = datetime.fromisoformat(when)
        except ValueError:
            since = None
    return Pending(current=cur, target=target, since=since)


# ------------------------------------------------------ 지금 껐다 켜도 되는가
#
# `apply()` 는 기다려 주지 않는다 — 돌고 있는 작업을 그대로 죽인다. 그래서 자동으로
# 적용하려면 **잃을 것이 없는 순간**을 골라야 한다. 판정 재료 둘:
#
#   1) 세션 기록(jsonl)이 조용한가 — 작업이 돌면 이 파일들이 계속 자란다.
#      **열려 있는 세션 수가 아니라 '쓰이고 있는가' 를 본다** — 답을 기다리며 떠 있는
#      세션은 죽어도 기록이 남아 이어서 열 수 있지만, 돌고 있는 작업은 통째로 날아간다.
#   2) 사람이 자리에 있는가 — 눈앞에서 창이 사라지면 그것대로 사고다.
#
# ★ 남는 구멍: **한 번의 도구 호출이 QUIET_MIN 보다 오래 걸리면**(긴 빌드 등) 그동안
#   기록이 안 쓰여 '조용함' 으로 보인다. 그래서 넉넉하게 잡았다. 더 줄이지 말 것.
QUIET_MIN = 45.0  # 세션 기록이 이만큼 조용해야 한다 (분)
IDLE_MIN = 20.0  # 사람 입력이 이만큼 없어야 한다 (분)

PROJECTS_DIR = os.path.join(os.path.expanduser("~"), ".claude", "projects")


def sessions_quiet_min() -> float:
    """세션 기록이 마지막으로 쓰인 뒤 지난 분. 기록이 하나도 없으면 무한대."""
    newest = 0.0
    try:
        for root, _dirs, files in os.walk(PROJECTS_DIR):
            for name in files:
                if not name.endswith(".jsonl"):
                    continue
                try:
                    m = os.path.getmtime(os.path.join(root, name))
                except OSError:
                    continue
                if m > newest:
                    newest = m
    except OSError:
        return 0.0  # 못 보면 '돌고 있다' 쪽으로 — 안전한 오답을 고른다
    if not newest:
        return float("inf")
    return max(0.0, (time.time() - newest) / 60.0)


def user_idle_min() -> float:
    """마지막 키보드·마우스 입력 뒤 지난 분. 못 재면 0(= 쓰는 중으로 본다)."""
    try:
        import ctypes

        class _Info(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        info = _Info()
        info.cbSize = ctypes.sizeof(info)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        # GetTickCount 는 49.7일마다 한 바퀴 돈다 — 음수가 나오면 0 으로 본다
        gap = ctypes.c_uint(ctypes.windll.kernel32.GetTickCount() - info.dwTime).value
        return max(0.0, gap / 60000.0)
    except Exception:  # noqa: BLE001
        return 0.0


def safe_now() -> tuple[bool, str]:
    """지금 껐다 켜도 잃을 것이 없나. 아니면 까닭을 함께 준다(그대로 보여 줄 수 있는 말)."""
    quiet = sessions_quiet_min()
    if quiet < QUIET_MIN:
        return False, f"{quiet:.0f}분 전까지 작업 중"
    idle = user_idle_min()
    if idle < IDLE_MIN:
        return False, f"{idle:.0f}분 전까지 쓰는 중"
    return True, ""


def _alive() -> int:
    out = _run(["tasklist", "/FI", f"IMAGENAME eq {IMAGE_NAME}", "/NH"], timeout=10)
    return out.count(IMAGE_NAME)


def apply(relaunch: bool = True) -> tuple[bool, str]:
    """클로드를 껐다 켜서 미뤄둔 등록을 지금 끝낸다.

    프로세스가 전부 빠지면 Windows 가 알아서 등록을 적용한다. 돌아오는 문구는
    사용자에게 그대로 보여 줄 수 있는 한 줄.
    """
    before = check()
    _run(["taskkill", "/F", "/T", "/IM", IMAGE_NAME], timeout=20)

    for _ in range(40):  # 20초까지 기다린다
        if _alive() == 0:
            break
        time.sleep(0.5)
    else:
        return False, "클로드가 안 닫힙니다 — 윈도우를 다시 시작해야 합니다"

    target = before.target if before else ""
    done = False
    for _ in range(60):  # 등록에 30초쯤 걸린다
        time.sleep(1.0)
        now = check()
        if now is None or (target and _ver(now.current) >= _ver(target)):
            done = True
            break

    if relaunch:
        try:
            os.startfile(APP_LINK)  # noqa: S606
        except OSError:
            _run(["explorer.exe", APP_LINK], timeout=10)

    if not target:
        return True, "클로드를 다시 켰습니다"
    if done:
        return True, f"업데이트 완료 — {target}"
    return True, f"클로드를 다시 켰습니다 — {target} 는 실행 시점에 적용됩니다"
