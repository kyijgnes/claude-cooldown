"""
스킨 공통 — 색·글꼴과 스킨이 지켜야 할 약속
=============================================
앱(cooldown_app.py)이 창·트레이·조회를 맡고, 스킨은 **그리기만** 한다.
스킨은 창을 만들지 않고, 네트워크를 치지 않고, 설정을 저장하지 않는다.
"""

from __future__ import annotations

import tkinter as tk

import cooldown_pack
from cooldown_core import Usage

# ---------------------------------------------------------------- 색
class Palette:
    """색 한 벌.

    스킨은 `from .base import P` 로 **이 객체를** 받아 두고 `P.bg` 처럼 쓴다.
    테마를 바꿀 때 객체를 갈아 끼우지 않고 **값만 덮어쓰므로**, 이미 받아 둔
    쪽도 함께 바뀐다. (값을 직접 import 하면 그 시점 색이 굳어 버린다)
    """

    def __init__(self, **colors: str):
        self.__dict__.update(colors)

    def copy_from(self, other: Palette) -> None:
        self.__dict__.update(other.__dict__)


# 작은 글자(8pt)가 많아 흐린 색도 배경 대비 4.5:1 이상으로 잡는다.
# 위계는 밝기가 아니라 글자 크기로 준다.
DARK = Palette(
    bg="#15171c",
    title="#e6edf3",
    label="#8b949e",  # 5.8:1
    sub="#c2cad4",
    faint="#7d8590",  # 4.8:1
    track="#252a32",  # 메인 화면 탭 바탕 등 면 색. 게이지 빈 칸은 gauge 를 쓴다
    gauge="#323844",  # 게이지 빈 칸. 바탕 1.5:1, 채운 초록과 4.6:1 · 빨강과 3.9:1
    line="#232830",
    green="#3fb950",
    amber="#e3b341",
    red="#ff5c61",
    red_bg="#2b1418",
    red_dim="#a67c83",  # red_bg 대비 4.8:1
    mascot="#d97757",  # 클로디 코랄. 바탕 5.7:1
    icon_text="#0d1117",  # 트레이 아이콘 숫자 (밝은 바탕 위)
)

LIGHT = Palette(
    bg="#f3f5f7",
    title="#12161b",
    label="#57606a",  # 5.0:1
    sub="#2f3742",
    faint="#616a75",  # 4.6:1
    track="#dce1e7",  # 메인 화면 탭 바탕 등 면 색. 게이지 빈 칸은 gauge 를 쓴다
    gauge="#c9d0d8",  # 게이지 빈 칸. 바탕 1.4:1, 채운 초록과 3.3:1 · 빨강과 3.4:1
    line="#e3e8ed",
    green="#1a7f37",
    amber="#8a6100",
    red="#cf222e",
    red_bg="#fff1ef",  # 위 초록 4.6 · 빨강 4.9 · faint 5.0:1
    red_dim="#8a5a5f",  # red_bg 대비 5.2:1
    mascot="#c4603f",  # 클로디 코랄을 밝은 바탕용으로 진하게. 바탕 3.8 · red_bg 3.8:1
    icon_text="#ffffff",  # 어두운 바탕 위
)

P = Palette(**DARK.__dict__)  # 지금 쓰는 한 벌

# 위젯 크기 배율 (메인 화면 > 위젯 모양 > 크기, 설정 `zoom`). 앱이 스킨을 짓기 직전에
# `set_zoom` 으로 정하고, 크기를 고칠 수 있는 스킨(카드·아크·표)은 build 첫머리에서
# 치수를 `z()`·글자를 `zf()` 로 키운다. 작업표시줄 바는 띠 높이를 따르므로 늘 1.0 이다.
ZOOMS = (0.9, 1.0, 1.25, 1.5)
_zoom = 1.0


def set_zoom(value: float) -> float:
    """배율을 정한다. 목록에 없는 값이면 1.0."""
    global _zoom
    _zoom = value if value in ZOOMS else 1.0
    return _zoom


def zoom() -> float:
    return _zoom


def z(n: float) -> int:
    """px 치수를 배율대로."""
    return int(round(n * _zoom))


def zf(size: int) -> int:
    """글자 크기(pt 는 양수, px 는 음수)를 배율대로. 부호는 그대로 둔다."""
    out = max(6, int(round(abs(size) * _zoom)))
    return -out if size < 0 else out


def dot_unit(base: int = 2) -> int:
    """클로디 도트 한 칸(px). 정수여야 도트가 고르게 찍힌다."""
    return max(base, int(base * _zoom + 0.5))

KR = "맑은 고딕"
NUM = "Segoe UI"


def system_prefers_light() -> bool:
    """윈도우의 '앱 모드' 설정이 밝게인가. 못 읽으면 어둡게로 본다."""
    try:
        import winreg

        path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            return bool(winreg.QueryValueEx(key, "AppsUseLightTheme")[0])
    except OSError:
        return False


def set_palette(kind: str) -> str:
    """'auto' / 'light' / 'dark' 를 받아 실제로 고른 쪽을 돌려준다."""
    picked = kind if kind in ("light", "dark") else (
        "light" if system_prefers_light() else "dark"
    )
    P.copy_from(LIGHT if picked == "light" else DARK)
    return picked


def taskbar_height(default: int = 48) -> int:
    """작업표시줄 높이(px). 못 재면 윈도우 11 기본값.

    작은 작업표시줄 설정이나 화면 배율에 따라 40~72px 사이로 달라진다.
    """
    try:
        import win32gui

        bar = win32gui.FindWindow("Shell_TrayWnd", None)
        if bar:
            _, top, _, bottom = win32gui.GetWindowRect(bar)
            height = bottom - top
            if 24 <= height <= 200:
                return height
    except Exception:  # noqa: BLE001
        pass
    return default


def tone(pct: float | None) -> str:
    """여유 초록 / 보통 노랑 / 임박 빨강. 테마에 맞는 색이 나온다."""
    if pct is None:
        return P.faint
    if pct < 50:
        return P.green
    if pct < 80:
        return P.amber
    return P.red


# '지금쯤' 눈금 — 주간 게이지 위에 세로로 긋는 가는 선. 색은 P.title(대비 최대)로
# 고정한다. 게이지 색(초록/노랑/빨강)을 쓰면 값처럼 보여 두 개를 헷갈린다.
MARK_W = 2


def pace_color(level: int) -> str:
    """속도 판정 색 — 0 넉넉 초록 / 1 주의 노랑 / 2 위험 빨강."""
    return (P.green, P.amber, P.red)[max(0, min(2, level))]


def mark_x(due: float, width: float) -> float:
    """게이지 폭 안에서 '지금쯤' 눈금이 설 x. 오른쪽 끝을 넘어가 잘리지 않게 당긴다."""
    x = width * max(0.0, min(100.0, due)) / 100
    return max(0.0, min(x, width - MARK_W))


def fill_w(pct: float | None, width: float) -> float:
    """게이지 폭 `width` 에서 `pct` 만큼 채울 길이. 눈금(`mark_x`)과 같은 잣대다 —
    쓴 양이 적정선과 같으면 채움 끝과 눈금이 한 자리에 선다. 메인 화면도 이걸 쓴다."""
    if not pct:
        return 0.0
    return width * max(0.0, min(100.0, pct)) / 100


def seg_fills(pct: float | None, count: int, pitch: float, seg_w: float) -> list[float]:
    """칸 게이지에서 칸마다 채울 길이(px). 칸 i 는 `i*pitch` 에서 시작해 `seg_w` 만큼이다.

    ★ 옛날엔 칸을 **통째로 켜고 끄기만**(`int(pct*n/100)`) 해서, 10칸 게이지면 57% 가 50% 로
      보였다. 눈금은 57% 자리에 서니 '적정선보다 덜 썼다' 로 읽혔다(메인 화면과 어긋남, 2026-11-15).
      이제 걸친 칸은 걸친 만큼만 채운다 — 채움 끝이 늘 `fill_w` 와 같은 자리다.
    지키는 것 둘: 꽉 찬 게이지는 100% 뿐(99% 는 마지막 칸 끝 1px 을 비운다),
    값이 있으면 아무리 작아도 첫 칸에 한 뼘은 보인다.
    """
    out = [0.0] * count
    if not pct or pct <= 0 or count <= 0:
        return out
    px = fill_w(pct, count * pitch)
    for i in range(count):
        out[i] = max(0.0, min(seg_w, px - i * pitch))
    out[0] = max(out[0], min(seg_w, 2.0))
    if pct < 100 and out[-1] >= seg_w:
        out[-1] = max(0.0, seg_w - 1)
    return out


def worst(usage: Usage) -> float | None:
    """두 한도 중 더 급한 쪽 — 한 개짜리 상태 표시에 쓴다."""
    values = [x for x in (usage.five.pct, usage.week.pct) if x is not None]
    return max(values) if values else None


def scoped_text(usage: Usage, limit: int = 2) -> str:
    """'Fable 7%' 처럼 모델별 한도를 한 줄로. 없으면 빈 문자열."""
    items = [s for s in usage.scoped if s.pct is not None][:limit]
    return "   ".join(f"{s.label} {s.pct:.0f}%" for s in items)


# ---------------------------------------------------------------- 약속


class Skin:
    """위젯 본체 한 가지 모양.

    앱은 `build()` 로 한 번 그리고, 이후 `show()` / `show_error()` 로만 값을 바꾼다.
    드래그·우클릭 바인딩은 앱이 자식 위젯을 훑어서 알아서 건다.
    """

    key = ""  # 설정 파일에 저장되는 식별자
    name = ""  # 우클릭 메뉴에 뜨는 이름
    width = 260  # 창 가로 폭(px). 세로는 내용에서 계산된다.
    dockable = False  # 작업표시줄에 붙일 수 있는가 (그 높이에 맞게 그리는 스킨만 참)

    def build(self, parent: tk.Misc) -> None:
        """`parent` 안에 위젯을 구성한다. 스킨 하나당 한 번만 불린다."""
        raise NotImplementedError

    def show(self, usage: Usage, stamp: str) -> None:
        """정상 값을 표시한다. `stamp` 는 '03:07' 형태의 갱신 시각."""
        raise NotImplementedError

    def show_error(self, text: str, keep_values: bool, stamp: str) -> None:
        """오류를 표시한다.

        `keep_values` 가 참이면 숫자·게이지는 건드리지 않는다 (일시적 연결 실패).
        거짓이면 값이 없다는 뜻이므로 비운다 (로그인이 막힘).
        """
        raise NotImplementedError

    def status_spot(self) -> tuple[int, int, str] | None:
        """상태 점(조회됨 초록 / 못 받음 빨강)을 놓을 자리 `(x, y, 바탕색)`.

        **앱이 그린다** — 새로고침 스피너가 같은 자리에서 그 둘레를 도는 링이라,
        둘을 한 캔버스에 두어야 겹쳐도 조화롭기 때문이다. 좌표는 **창 기준 한가운데**.
        `None`(기본)이면 점 없이 스피너만, 옛날처럼 오른쪽 위 구석에 잠깐 뜬다 —
        기준 시각을 글자로 보여 주는 스킨은 점이 필요 없다.
        """
        return None

    def react(self, x: float | None = None, y: float | None = None) -> None:
        """위젯을 눌렀을 때의 반응(선택). `x`/`y` 는 창 기준 누른 자리(스킨이 쓰면).
        기본은 아무것도 하지 않는다."""
        pass

    def absorbed(self) -> bool:
        """마지막 누르기를 스킨이 '놀이' 로 가져갔는가(선택).

        참이면 앱은 그 클릭으로 **새로고침을 하지 않는다** — 마스코트를 두드리며 노는
        것과 값을 다시 받아 오는 것은 다른 일이다. 기본은 거짓(누르면 새로고침).
        """
        return False

    def hold(self, x: float, y: float) -> None:
        """그 자리에서 계속 누르고 있을 때(선택). 앱이 `HOLD_MS` 뒤 한 번만 부른다.
        끌기로 바뀌면 안 부른다. 기본은 아무것도 하지 않는다."""
        pass

    def let_go(self) -> None:
        """`hold()` 뒤에 손을 뗐을 때(선택). 끌기로 접힐 때도 불린다."""
        pass

    # ---------------------------------------------- 바 캐릭터 상호작용 (11-20)
    # 캐릭터(클로디·팩 캐릭터)가 있는 스킨은 `self.claudi` 를 두면 아래가 그대로 넘긴다.
    # 캐릭터 없는 스킨은 전부 아무 일 없음(`catch` 거짓 = 끌면 창이 움직인다).
    def _char(self):
        return getattr(self, "claudi", None)

    def catch(self, x: float, y: float) -> bool:
        """창 기준 (x, y) 를 누른 것이 캐릭터 위인가. 참이면 앱은 끌 때 **창 대신 캐릭터**를 끈다."""
        ch = self._char()
        if ch is None or not hasattr(ch, "catch"):
            return False
        return bool(ch.catch(*ch.to_local(self, x, y)))

    def drag(self, x: float, y: float) -> None:
        """캐릭터를 끄는 중. 창 기준 마우스 자리(앱이 끌 때마다 부른다)."""
        ch = self._char()
        if ch is not None and hasattr(ch, "drag"):
            ch.drag(*ch.to_local(self, x, y))

    def put_down(self) -> None:
        """끌던 캐릭터를 놓았다. 캐릭터가 제자리로 돌아간다."""
        ch = self._char()
        if ch is not None and hasattr(ch, "put_down"):
            ch.put_down()

    def wheel(self, x: float, y: float, delta: int) -> None:
        """캐릭터 위에서 마우스 휠을 굴렸다 (창 기준 자리, 위로 굴리면 delta > 0)."""
        ch = self._char()
        if ch is not None and hasattr(ch, "wheel"):
            ch.wheel(*ch.to_local(self, x, y), delta)

    def middle(self, x: float, y: float) -> None:
        """캐릭터를 가운데 단추로 눌렀다 (창 기준 자리, 11-21 하트). 캐릭터 밖이면 아무 일 없음."""
        ch = self._char()
        if ch is not None and hasattr(ch, "middle"):
            ch.middle(*ch.to_local(self, x, y))

    def set_away(self, away: bool) -> None:
        """PC 입력이 한참 없다(참) / 돌아왔다(거짓). 앱의 `AwayWatch` 가 바뀔 때만 부른다."""
        ch = self._char()
        if ch is not None and hasattr(ch, "set_away"):
            ch.set_away(away)

    def feel(self, usage: Usage) -> None:
        """사용량을 캐릭터 기분으로 넘긴다(스킨의 `show` 가 부른다). 5시간 한도가 풀렸으면 축하."""
        ch = self._char()
        if ch is None or not hasattr(ch, "set_mood"):
            return
        ch.set_mood(char_mood(usage.five.pct, usage.week.pct))
        if hasattr(ch, "note_usage"):  # 사용량이 짧은 새 크게 뛰면 당황
            ch.note_usage(usage.five.pct)
        before = getattr(self, "_feel_five", None)
        if cooldown_pack.was_reset(before, usage.five.pct) and hasattr(ch, "celebrate"):
            ch.celebrate()
        self._feel_five = usage.five.pct

    def feel_error(self) -> None:
        """조회 오류를 캐릭터 기분으로(스킨의 `show_error` 가 부른다)."""
        ch = self._char()
        if ch is not None and hasattr(ch, "set_mood"):
            ch.set_mood("오류")

    def notice(self, text: str) -> None:
        """값은 멀쩡한데 알릴 것(예: 자동 시작 놓침)을 표시(선택). 기본은 no-op.

        오류(show_error)보다 낮은 우선순위 — 앱은 **오류가 없을 때만** 부른다.
        앱은 show()/show_error() 로 화면을 그린 **직후** 이걸 부르므로, `text` 가
        빈 문자열이면 스킨은 아무것도 하지 않는다(직전에 정상값이 이미 자리를 되돌렸다).
        네 상태의 창 높이가 같아야 하므로 **자리를 새로 만들지 말고** 이미 있는
        요소(꼬리말·제목 등)의 글자·색만 바꿔서 표현한다."""
        pass

    def notice_at(self, x: float, y: float) -> bool:
        """창 기준 (x, y) 가 지금 떠 있는 알림 문구 위인가(선택). 앱은 쿨다운 새 버전
        문구가 떠 있을 때만 묻고, 참이면 메인 화면 대신 곧바로 업데이트한다. 기본은 거짓."""
        return False


def inside(widget: tk.Misc, x: float, y: float, pad: int = 4) -> bool:
    """창 기준 (x, y) 가 `widget` 의 보이는 네모 안인가 (둘레 `pad` px 까지 봐준다)."""
    try:
        if not widget.winfo_ismapped():
            return False
        top = widget.winfo_toplevel()
        x0 = widget.winfo_rootx() - top.winfo_rootx()
        y0 = widget.winfo_rooty() - top.winfo_rooty()
        return (x0 - pad <= x <= x0 + widget.winfo_width() + pad
                and y0 - pad <= y <= y0 + widget.winfo_height() + pad)
    except tk.TclError:
        return False


# ---------------------------------------------------------------- 캐릭터 공용 셈
CALM_AT = 50.0      # 이보다 낮으면 「여유」, 넘으면 「보통」 (80 넘으면 허둥, 한도면 잠)
AWAY_AFTER = 300.0  # PC 입력이 이만큼(초) 없으면 자리비움
# 자꾸 누르기(11-20 둘째): 누를 때마다 1 씩 쌓이고 초마다 ANNOY_COOL 만큼 식는다.
# 쌓인 만큼 짜증 → 화남 → 포기. 2초에 한 번 꼴로 누르는 것(새로고침)은 안 쌓인다.
ANNOY_STEPS = (8.0, 16.0, 26.0)  # 짜증 · 화남 · 포기에 닿는 쌓임 (11-20 셋째: 작정하고 연타해야 닿게)
ANNOY_COOL = 0.8
ANNOY_NAMES = ("", "짜증", "화남", "포기")
# 흔들기 기절: 끄는 동안 SHAKE_WINDOW 초 안에 방향을 SHAKE_TURNS 번 넘게 바꾸고(한 번 휘두를 때
# SHAKE_SWING px 넘게), 그동안 SHAKE_SPEED px/초 넘게 빨리 움직였으면 어지럽다.
# 11-20 넷째(흔들어도 기절을 안 한다): 옛 기준(6번·1.5초 내내 초당 700px)은 작정하고 흔들어도 안 걸렸다.
# 좌우로 2~3번 세게 흔들면(방향 바뀜 3번) 걸리게 낮추고, 빠르기는 흔든 동안만 잰다.
SHAKE_SWING = 24.0
SHAKE_TURNS = 3
SHAKE_WINDOW = 1.2
SHAKE_SPEED = 380.0
SHAKE_KEEP = 3.0  # 다 흔든 뒤 이만큼 안에 놓아야 기절 (가만 들고 있으면 정신 차린다)


def char_mood(five: float | None, week: float | None) -> str:
    """사용량 → 캐릭터 기분 네 단계: 여유 · 보통 · 허둥 · 잠."""
    m = cooldown_pack.mood(five, week)
    worst = max((p for p in (five, week) if p is not None), default=0.0)
    if m == "여유" and worst >= CALM_AT:
        return "보통"
    return m


class Annoy:
    """자꾸 누른 정도 → 단계 0(괜찮음)·1(짜증)·2(화남)·3(포기). 시계는 바깥에서 받는다(시험용).
    포기에 닿으면 쌓인 것을 비운다(체념하고 나면 처음부터)."""

    def __init__(self, steps=ANNOY_STEPS, cool: float = ANNOY_COOL):
        self.steps, self.cool = steps, cool
        self.heat = 0.0
        self.t: float | None = None

    def _cool(self, now: float) -> None:
        if self.t is not None:
            self.heat = max(0.0, self.heat - self.cool * max(0.0, now - self.t))
        self.t = now

    def level(self, now: float) -> int:
        self._cool(now)
        return sum(self.heat >= s for s in self.steps)

    def tap(self, now: float) -> int:
        """한 번 눌렀다. 지금 단계를 낸다(3 이면 포기, 쌓인 것은 비운다)."""
        self._cool(now)
        self.heat += 1.0
        got = sum(self.heat >= s for s in self.steps)
        if got >= 3:
            self.heat = 0.0
        return got

    def reset(self) -> None:
        self.heat = 0.0


class Shake:
    """끄는 동안 마우스를 마구 흔들었나. `feed(x, y, now)` 를 끌 때마다, `dizzy(now)` 로 묻는다.
    좌우·위아래를 따로 보아 방향이 바뀐 때를 세고(휘두른 폭이 SHAKE_SWING 넘을 때만), 빠르기도 본다."""

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self.last: tuple[float, float, float] | None = None
        self.peak = [0.0, 0.0]
        self.dir = [0, 0]
        self.turns: list[float] = []
        self.path: list[tuple[float, float]] = []  # (때, 움직인 거리)
        self.hit_at: float | None = None

    def feed(self, x: float, y: float, now: float) -> bool:
        """끈 자리 하나를 받는다. 이번에 **새로** 어지러워졌으면 참 (잡은 채로 헤롱 그림으로 바꾸게)."""
        was = self.dizzy(now)
        if self.last is not None:
            lx, ly, _ = self.last
            self.path.append((now, ((x - lx) ** 2 + (y - ly) ** 2) ** 0.5))
        else:
            self.peak = [x, y]
        self.last = (x, y, now)
        for i, v in enumerate((x, y)):
            d = self.dir[i]
            if d == 0:
                if abs(v - self.peak[i]) >= SHAKE_SWING:
                    self.dir[i] = 1 if v > self.peak[i] else -1
                    self.peak[i] = v
            elif (v - self.peak[i]) * d > 0:
                self.peak[i] = v
            elif abs(v - self.peak[i]) >= SHAKE_SWING:
                self.turns.append(now)
                self.dir[i] = -d
                self.peak[i] = v
        self.turns = [t for t in self.turns if now - t <= SHAKE_WINDOW]
        self.path = [p for p in self.path if now - p[0] <= SHAKE_WINDOW]
        span = max(0.25, now - self.path[0][0]) if self.path else SHAKE_WINDOW
        speed = sum(d for _, d in self.path) / span
        if len(self.turns) >= SHAKE_TURNS and speed >= SHAKE_SPEED:
            self.hit_at = now
        return self.dizzy(now) and not was

    def dizzy(self, now: float) -> bool:
        return self.hit_at is not None and now - self.hit_at <= SHAKE_KEEP


def idle_seconds() -> float:
    """윈도우에서 마지막 키보드·마우스 입력 뒤 흐른 초 (`GetLastInputInfo`). 못 재면 0."""
    try:
        import ctypes
        from ctypes import wintypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        now = ctypes.windll.kernel32.GetTickCount() & 0xFFFFFFFF
        return ((now - info.dwTime) & 0xFFFFFFFF) / 1000.0
    except Exception:  # noqa: BLE001  윈도우가 아니거나 막혀 있으면 자리비움을 안 쓴다
        return 0.0


class AwayWatch:
    """PC 입력이 `after` 초 넘게 없으면 자리비움. `poll()` 은 바뀐 순간에만 새 값을, 아니면 None."""

    def __init__(self, idle_fn=idle_seconds, after: float = AWAY_AFTER):
        self.idle_fn = idle_fn
        self.after = after
        self.away = False

    def poll(self) -> bool | None:
        now_away = self.idle_fn() >= self.after
        if now_away == self.away:
            return None
        self.away = now_away
        return now_away

