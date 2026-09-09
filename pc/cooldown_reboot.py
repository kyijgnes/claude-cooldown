"""윈도우 업데이트 재시작 대기 감시 — Tk 없음.

**왜 있나.** 윈도우 업데이트는 새 판을 깔아 두고 재시작을 기다린다. 그 재시작은
'활성 시간' 밖이면 **묻지도 않고** 일어난다 — 2026-09-09 12:29 에 그렇게 당했다.
활성 시간이 18~12 로 잡혀 있어서 낮 12시가 되자마자 창이 열렸고, 오전 7:37 에 깔아
둔 세 판(KB5126052·KB5124007·KB5124008)을 적용하느라 **연달아 세 번** 재시작했다.
돌아가던 클로드 세션은 그 자리에서 통째로 날아갔다.

대기 중인 걸 미리 알면 편할 때 직접 재시작해서 피할 수 있다. 이 파일은 그 판정만 한다.
클로드 앱 쪽 대기는 `cooldown_update` 가 따로 본다 — 남의 프로세스를 죽이는 그쪽과 달리
여기는 **읽기만** 한다.

레지스트리만 읽으므로 관리자 권한도, 프로세스 실행도 필요 없다(1ms 안쪽). 그래서
따로 스레드를 두지 않고 Tk 차례에서 그냥 부른다.
"""

from __future__ import annotations

import os
import re
import winreg
from dataclasses import dataclass
from datetime import datetime, timedelta

HKLM = winreg.HKEY_LOCAL_MACHINE
# 64비트 윈도우에서 32비트로 묶여도 같은 곳을 보게 못박는다. 이 값들은 전부
# 64비트 쪽에만 있어서, 리다이렉션에 걸리면 **조용히 '대기 없음'** 이 된다.
_READ = winreg.KEY_READ | winreg.KEY_WOW64_64KEY

# 재시작을 기다리는가 — 둘 중 하나만 있어도 대기다.
#   · WindowsUpdate\...\RebootRequired : 윈도우 업데이트가 세운 팻말 (이게 본디것)
#   · CBS\RebootPending                : 구성 요소 서비스(서비스 스택)가 세운 팻말
_WU_REBOOT = r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired"
_CBS = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing"
_CBS_REBOOT = _CBS + r"\RebootPending"
_CBS_PACKAGES = _CBS + r"\PackagesPending"

# ★★ `Session Manager\PendingFileRenameOperations` 는 **쓰지 않는다.** 재시작 때
#   옮길 파일 목록일 뿐이라 평상시에도 늘 차 있다(이 PC 는 지금도 32줄). 그걸 대기로
#   보면 위젯에 경고가 하루 종일 떠 있게 된다 — 그러면 아무도 안 본다.

# 활성 시간 = **재시작하지 않는 시간**. 사람이 정한 것(UX\Settings)과 회사 정책으로
# 내려온 것(Policies)이 따로 있고, 정책이 있으면 그쪽이 이긴다.
_UX = r"SOFTWARE\Microsoft\WindowsUpdate\UX\Settings"
_POLICY = r"SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate"

# 1601-01-01 부터 1970-01-01 까지의 100나노초 수 — 레지스트리 시각을 초로 옮길 때 쓴다
_FT_EPOCH = 116_444_736_000_000_000

# 손으로 확인할 때만 쓰는 뒷문 — 진짜 업데이트가 밀릴 때까지 기다리지 않고
# 위젯·알림이 어떻게 뜨는지 보려고 둔다. 켜면 `check()` 가 가짜 대기를 돌려준다.
_FAKE_ENV = "COOLDOWN_FAKE_REBOOT"


@dataclass(frozen=True)
class Pending:
    """재시작을 기다리고 있는 윈도우 업데이트."""

    since: datetime | None  # 팻말이 세워진 때 (모르면 None)
    risk_at: datetime | None  # 이때부터 윈도우가 알아서 재시작한다 (지금이면 '임박')
    kbs: tuple[str, ...] = ()  # 기다리는 업데이트 번호 (알아냈을 때만)

    @property
    def imminent(self) -> bool:
        """지금이 이미 재시작해도 되는 시간대인가 — 언제 꺼져도 이상하지 않다."""
        return self.risk_at is not None and self.risk_at <= datetime.now()

    @property
    def short(self) -> str:
        """위젯의 좁은 알림 자리에 얹을 문구. 시각을 앞세운 명사형 한 줄."""
        if self.risk_at is None:
            return "윈도우 재시작 대기"
        if self.imminent:
            return "윈도우 재시작 임박"
        return f"{self.risk_at:%H시} 윈도우 재시작"

    @property
    def line(self) -> str:
        """트레이 알림 첫 줄 — 무엇이 몇 건 밀려 있는지."""
        if not self.kbs:
            return "윈도우 업데이트 재시작 대기"
        if len(self.kbs) == 1:
            return f"윈도우 업데이트 재시작 대기 ({self.kbs[0]})"
        return f"윈도우 업데이트 재시작 대기 ({self.kbs[0]} 등 {len(self.kbs)}건)"

    @property
    def when(self) -> str:
        """트레이 알림 둘째 줄 — 언제 꺼지는가. 이게 이 기능의 알맹이다."""
        if self.risk_at is None:
            return "윈도우가 알아서 재시작합니다"
        if self.imminent:
            return "지금 언제든 윈도우가 알아서 재시작합니다"
        return f"{self.risk_at:%H:%M} 부터 윈도우가 알아서 재시작합니다"

    @property
    def sig(self) -> str:
        """같은 대기인지 가리는 표. 알림을 한 번만 띄우는 데 쓴다."""
        return "+".join(self.kbs) or (f"{self.since:%m-%d %H:%M}" if self.since else "?")


# ------------------------------------------------------------------ 레지스트리


def _key_exists(path: str) -> bool:
    try:
        winreg.CloseKey(winreg.OpenKey(HKLM, path, 0, _READ))
        return True
    except OSError:
        return False


def _key_time(path: str) -> datetime | None:
    """그 열쇠가 마지막으로 고쳐진 때 = 팻말이 세워진 때."""
    try:
        with winreg.OpenKey(HKLM, path, 0, _READ) as k:
            ft = winreg.QueryInfoKey(k)[2]
        return datetime.fromtimestamp((ft - _FT_EPOCH) / 10_000_000)
    except (OSError, ValueError, OverflowError):
        return None


def _dword(path: str, name: str) -> int | None:
    try:
        with winreg.OpenKey(HKLM, path, 0, _READ) as k:
            val, kind = winreg.QueryValueEx(k, name)
        return int(val) if kind == winreg.REG_DWORD else None
    except (OSError, ValueError, TypeError):
        return None


def pending_kbs() -> tuple[str, ...]:
    """재시작을 기다리는 업데이트 번호. 못 읽으면 빈 것 — 없다는 뜻이 아니다."""
    out: list[str] = []
    try:
        with winreg.OpenKey(HKLM, _CBS_PACKAGES, 0, _READ) as k:
            for i in range(winreg.QueryInfoKey(k)[0]):
                m = re.search(r"KB\d{6,}", winreg.EnumKey(k, i), re.I)
                if m:
                    out.append(m.group(0).upper())
    except OSError:
        pass
    return tuple(dict.fromkeys(out))  # 겹치는 것만 덜어내고 차례는 그대로


# ------------------------------------------------------------------ 활성 시간


def active_hours() -> tuple[int, int] | None:
    """(시작, 끝) 24시간 — **이 사이엔 재시작하지 않는다.** 못 읽으면 None.

    18~12 처럼 자정을 넘겨 걸치는 것이 오히려 흔하다(밤에 안 꺼지게 하려고).
    그러면 남는 12~18 이 재시작 창이 된다 — 낮에 일하는 사람에겐 정반대다.
    """
    for path in (_POLICY, _UX):  # 회사 정책이 있으면 그쪽이 이긴다
        start, end = _dword(path, "ActiveHoursStart"), _dword(path, "ActiveHoursEnd")
        if start is not None and end is not None and 0 <= start < 24 and 0 <= end < 24:
            return start, end
    return None


def _in_active(now: datetime, start: int, end: int) -> bool:
    h = now.hour
    return start <= h < end if start <= end else (h >= start or h < end)


def next_risk(now: datetime | None = None) -> datetime | None:
    """재시작 창이 다음에 열리는 때. 이미 열려 있으면 지금. 모르면 None.

    None 은 '안전' 이 아니라 **모른다**는 뜻이다 — 활성 시간을 안 정해 두면 윈도우가
    제 기본값으로 도는데, 그 값은 여기 안 적혀 있다.
    """
    now = now or datetime.now()
    hours = active_hours()
    if hours is None:
        return None
    start, end = hours
    if start == end:  # 하루 종일 활성 — 윈도우가 안 받아 주는 값이지만 막아 둔다
        return None
    if not _in_active(now, start, end):
        return now  # 지금이 이미 창 안이다
    opens = now.replace(hour=end, minute=0, second=0, microsecond=0)
    if opens <= now:
        opens += timedelta(days=1)
    return opens


# ------------------------------------------------------------------ 판정


def check() -> Pending | None:
    """재시작을 기다리고 있으면 Pending, 아니면 None. 레지스트리만 읽는다."""
    if os.environ.get(_FAKE_ENV):  # 손으로 확인할 때만
        return Pending(datetime.now(), next_risk(), ("KB0000000", "KB0000001"))
    marks = [p for p in (_WU_REBOOT, _CBS_REBOOT) if _key_exists(p)]
    if not marks:
        return None
    stamps = [t for t in (_key_time(p) for p in marks) if t is not None]
    return Pending(min(stamps) if stamps else None, next_risk(), pending_kbs())


# ---------------------------------------------------------------- 단독 확인
# 위젯 없이 지금 상태만 보고 싶을 때:  python cooldown_reboot.py
# 위젯이 어떻게 뜨는지 보려면 가짜로:   set COOLDOWN_FAKE_REBOOT=1

if __name__ == "__main__":
    hours = active_hours()
    print("활성 시간 :", f"{hours[0]}시 ~ {hours[1]}시 (이 사이엔 재시작 안 함)" if hours else "안 정해 둠")
    nxt = next_risk()
    print("재시작 창 :", "지금 열려 있음" if nxt and nxt <= datetime.now() else (f"{nxt:%m-%d %H:%M} 부터" if nxt else "모름"))
    p = check()
    if p is None:
        print("대기      : 없음")
    else:
        print("대기      :", p.line)
        print("  세워진 때:", f"{p.since:%m-%d %H:%M}" if p.since else "모름")
        print("  위젯 문구:", p.short)
        print("  알림 둘째줄:", p.when)
