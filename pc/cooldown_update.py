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
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime

# 클로드 앱 식별자 — 실행·종료·등록에 쓴다
PUB_ID = "pzs8sxrjxfjjc"  # 게시자 꼬리표. 패키지 이름·가족 이름·폴더 이름에 다 들어간다
APP_LINK = rf"shell:AppsFolder\Claude_{PUB_ID}!Claude"
PKG_FAMILY = f"Claude_{PUB_ID}"  # 등록할 때 쓰는 가족 이름
PKG_ROOT = r"C:\Program Files\WindowsApps"  # 받아 둔 판이 앉아 있는 곳
IMAGE_NAME = "Claude.exe"
# ★★ **이름으로 죽이지 않는다.** 클로드 코드 CLI 도 실행 파일 이름이 `claude.exe` 이고
#   `taskkill /IM` 은 대소문자를 안 가린다 — `taskkill /F /T /IM Claude.exe` 는
#   **돌고 있는 세션·원격 대기(`claude rc`)·핑까지 같이 죽였다**(2026-08-14 에 실제로
#   그랬다: 자동 적용이 5분마다 돌면서 원격 대기를 세 번 죽여 스스로 꺼졌고, 폰에서
#   이 PC 에 세션을 열 수 없게 됐다). 데스크톱 앱은 MSIX 라 **패키지 폴더 안에서**
#   돌므로, 죽일 것은 그 경로로 고른다. 되돌리지 말 것.
PKG_MARK = r"\WindowsApps\Claude_"

_NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW — 콘솔 없는 앱이라 창이 뜨면 안 된다


@dataclass(frozen=True)
class Pending:
    """등록을 기다리고 있는 업데이트."""

    current: str  # 지금 돌고 있는 버전
    target: str  # 등록을 기다리는 버전
    since: datetime | None  # 내려받은 시각 (모르면 None)
    # 윈도우가 실제로 '등록을 미뤄 뒀나'(이벤트 658). 거짓이면 업데이터가 새 판을
    # **봤다는 것뿐**(`updaterLastSeenVersion`)이라, 껐다 켜도 끝날 것이 없을 수 있다.
    # 자동 적용은 참일 때만 한다 — 아래 '자동으로 적용해도 되는가' 참고.
    staged: bool = False

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
# ★ 같은 앱이 여러 판 등록돼 있을 수 있다. 그때 Get-AppxPackage 는 여러 줄을 주고,
#   그걸 문자열로 이어 붙이면 "1.26832.0.0 1.30096.1.0" 이 되어 _ver() 이 앞의(=옛)
#   판으로 읽는다 — 새 판이 이미 등록됐는데도 '대기 중' 이 영영 안 풀린다.
#   **가장 높은 판**을 지금 판으로 본다.
$cur = (Get-AppxPackage -Name Claude | Sort-Object { [version]$_.Version } |
        Select-Object -Last 1).Version
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

    def _highest(values) -> str:
        best = ""
        for v in values:
            v = (v or "").strip()
            if _ver(v) > _ver(cur) and (not best or _ver(v) > _ver(best)):
                best = v
        return best

    # 두 신호를 **가른다**. 이벤트 658 = 윈도우가 등록을 실제로 미뤄 둔 것(껐다 켜면
    # 끝난다), `updaterLastSeenVersion` = 업데이터가 새 판을 봤다는 것뿐(아직 안
    # 내려받았을 수 있어 껐다 켜도 끝날 것이 없다).
    staged_target = _highest(cands)
    seen_target = _highest([data.get("seen") or ""])
    target = staged_target or seen_target
    if not target:
        return None

    since = None
    when = (data.get("when") or "").strip()
    if when:
        try:
            since = datetime.fromisoformat(when)
        except ValueError:
            since = None
    return Pending(
        current=cur, target=target, since=since, staged=bool(staged_target)
    )


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


# 등록 명령을 기다려 주는 시간(초). 등록 자체는 ~31초인데 파일이 많으면 더 걸린다.
REGISTER_WAIT = 180


def _desktop_pids() -> list[int]:
    """돌고 있는 **데스크톱 앱**(MSIX 패키지) 프로세스 번호들.

    ★ 이름이 아니라 **경로**로 고른다 — 클로드 코드 CLI 도 `claude.exe` 라서
    이름으로 고르면 돌고 있는 세션·원격 대기·핑까지 딸려 들어간다(맨 위 참고).
    거꾸로 **이름은 안 본다** — 패키지 폴더 안에서 도는 것은 이름이 무엇이든 한 식구라,
    하나라도 남아 있으면 등록이 `0x80073D02` 로 튕긴다.
    """
    out = _ps(
        "@(Get-CimInstance Win32_Process | "
        "Where-Object { $_.ExecutablePath -like '*" + PKG_MARK + "*' } | "
        "ForEach-Object { $_.ProcessId }) -join ','",
        timeout=25,
    )
    pids = []
    for chunk in (out or "").replace("\n", ",").split(","):
        chunk = chunk.strip()
        if chunk.isdigit():
            pids.append(int(chunk))
    return pids


def _alive() -> int:
    return len(_desktop_pids())


# ------------------------------------------------------------ 등록을 직접 부른다
#
# ★★★ **윈도우는 프로세스가 다 빠져도 스스로 등록하지 않는다.** 2026-08-19 에 하루를
# 통째로 날리고 알아낸 것 — 미뤄둔 등록을 처리하는 것은 **앱을 다음에 켤 때**
# (이벤트 679 `OnDemandRegisterPackageList`)인데, 그때는 앱이 이미 떠 있어
# **`0x80073D02` (앱을 닫아야 하므로 설치할 수 없습니다)** 로 깨진다. 그래서 옛
# `apply()` 는 다 죽여 놓고 120초를 헛기다리다 '안 바뀌었습니다' 로 접었고(등록을 부를
# 사람이 아무도 없었다), 곧바로 앱을 다시 켜서 **다음 기회까지 막아** 버렸다.
# 켜져 있어서 안 되고 꺼져 있어서 안 되는 꼴이었다.
#
# 빠져나가는 길은 하나뿐이다 — **다 죽은 그 틈에 등록을 우리가 부른다.**
# 관리자 권한은 필요 없다(실측). 되돌리지 말 것.
_REG_TRY = "$ErrorActionPreference='Stop'; try {{ {cmd}; 'OK' }} catch {{ $_.Exception.Message }}"

# 파워셸 오류 문구는 콘솔 코드페이지(cp949)로 나와 utf-8 로 읽으면 깨진다. 그래서
# **HRESULT 만 뽑아** 우리 말로 바꿔 준다 — 코드는 어느 코드페이지에서나 ASCII 다.
_HRESULT = re.compile(r"0x[0-9A-Fa-f]{8}")
_WHY = {
    "0x80073D02": "클로드가 아직 떠 있습니다",
    "0x80073CF9": "등록에 실패했습니다",
    "0x80073CFB": "이미 같은 판이 등록돼 있습니다",
}


_CUR_PS = (
    "$p = Get-AppxPackage -Name Claude | Sort-Object { [version]$_.Version } | "
    "Select-Object -Last 1; if ($p) { $p.Version }"
)
_VERLIKE = re.compile(r"^\d+(\.\d+)+$")


def installed_version() -> str:
    """지금 등록돼 있는 판. **못 읽었으면 빈 문자열**(= 모른다).

    ★ `check()` 를 성공 판정에 쓰면 안 된다 — 그건 '대기 없음' 과 '못 물어봤음' 이
    똑같이 `None` 이라, 파워셸이 한 번 튕긴 밤에 **등록이 깨졌는데 '업데이트 완료'** 라고
    말하게 된다. 여기서는 **판 번호를 눈으로 읽었을 때만** 그 값을 준다.
    """
    for line in _ps(_CUR_PS, timeout=25).splitlines():
        line = line.strip()
        if _VERLIKE.match(line):
            return line
    return ""


def register(target: str = "") -> tuple[bool, str]:
    """받아 둔 판을 **지금** 등록한다. 프로세스가 전부 빠진 뒤에 부를 것.

    두 길을 차례로 해 본다. 먼저 **판 번호로 폴더를 짚어** 등록하고(윈도우가 스스로 할
    때와 같은 길이다 — 이벤트 854 에 그 `AppxManifest.xml` 이 찍힌다), 폴더가 없거나
    거절당하면 **가족 이름**으로 받아 둔 판을 찾아 등록한다.
    """
    cmds = []
    if target:
        manifest = os.path.join(
            PKG_ROOT, f"Claude_{target}_x64__{PUB_ID}", "AppxManifest.xml"
        )
        if os.path.exists(manifest):
            cmds.append(f"Add-AppxPackage -DisableDevelopmentMode -Register '{manifest}'")
    cmds.append(f"Add-AppxPackage -RegisterByFamilyName -MainPackage '{PKG_FAMILY}'")

    why = ""
    for cmd in cmds:
        out = _ps(_REG_TRY.format(cmd=cmd), timeout=REGISTER_WAIT).strip()
        if out.startswith("OK"):
            return True, ""
        code = _HRESULT.search(out)
        why = _WHY.get(code.group(0), f"등록 오류 {code.group(0)}") if code else "등록이 안 됐습니다"
    return False, why


def apply(relaunch: bool = True, target: str = "") -> tuple[bool, str]:
    """클로드를 닫고 **등록까지 끝낸 뒤** 다시 켠다.

    셋을 순서대로 한다: 데스크톱 앱만 죽이기 → `register()` → 다시 켜기.
    돌아오는 문구는 사용자에게 그대로 보여 줄 수 있는 한 줄.

    ★ **끝났을 때만 True** 다. 판이 안 바뀌었으면 False — 부르는 쪽이 그걸 보고
    같은 판을 몇 번이고 되풀이하지 않는다(안 그러면 5분마다 클로드를 죽인다.
    2026-08-14 새벽에 밤새 그랬다).

    ★★ **어느 판을 올릴지는 부르는 쪽이 준다.** 여기서 다시 물어보게 두면, 그 물음
    한 번이 헛돌았을 때(`check()` 는 **못 물어봤을 때도 None** 이다) 올릴 판을 모르는
    채로 **죽이기만 하고 등록은 건너뛰고서 '다 됐다'** 고 말하게 된다. 모르면 아무것도
    하지 않는다 — 남의 앱을 죽이는 일에 '아마' 는 없다.
    """
    if not target:
        before = check()
        target = before.target if before else ""
    if not target:
        return False, "대기 중인 업데이트를 못 찾았습니다"

    pids = _desktop_pids()
    for pid in pids:
        _run(["taskkill", "/F", "/PID", str(pid)], timeout=15)

    for _ in range(40):  # 20초까지 기다린다
        if _alive() == 0:
            break
        time.sleep(0.5)
    else:
        return False, "클로드가 안 닫힙니다 — 윈도우를 다시 시작해야 합니다"

    _ok, why = register(target)

    # 켜기 **전에** 본다 — 앱이 뜨면 다시 물고 있어 판정이 흐려진다.
    # ★★ **끝났다는 말은 판 번호를 읽었을 때만 한다.** 등록 명령이 'OK' 를 줘도 그것이
    #   곧 새 판은 아니고(`-RegisterByFamilyName` 은 같은 판을 다시 등록해도 OK 다),
    #   `check()` 의 None 은 '대기 없음' 과 '못 물어봤음' 을 가리지 못한다. 못 읽었으면
    #   **안 끝난 것으로 친다** — 이쪽으로 틀리면 30분 뒤에 한 번 더 해 볼 뿐이지만,
    #   반대로 틀리면 깨진 밤에 '업데이트 완료' 라고 말하고 손을 놓는다.
    cur = installed_version()
    done = bool(cur) and _ver(cur) >= _ver(target)

    if relaunch:
        try:
            os.startfile(APP_LINK)  # noqa: S606
        except OSError:
            _run(["explorer.exe", APP_LINK], timeout=10)

    if done:
        return True, f"업데이트 완료 — {target}"
    return False, f"{target} 등록이 안 됐습니다 — {why or '판이 안 바뀌었습니다'}"


# ---------------------------------------------------------------- 단독 확인
#     python cooldown_update.py          지금 판정만 (아무것도 안 죽인다)

if __name__ == "__main__":
    p = check()
    if p is None:
        print("대기 중인 업데이트 없음")
    else:
        print(f"지금 {p.current} → 대기 {p.target}")
        print("등록 지연됨(이벤트 658):", "예" if p.staged else "아니오 (업데이터가 본 판)")
        print("내려받은 시각:", f"{p.since:%m-%d %H:%M}" if p.since else "모름")
    ok, why = safe_now()
    print("지금 껐다 켜도 되나:", "예" if ok else f"아니오 — {why}")
    print("데스크톱 앱 프로세스:", len(_desktop_pids()), "개")
