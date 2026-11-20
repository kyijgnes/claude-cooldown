"""바 캐릭터·클로디 상호작용(11-20) 상태 전이 시험. 가짜 시계·가짜 입력으로 돈다.

자꾸 누르기 → 짜증·화남·포기 · 흔들기 → 헤롱 기절 · 끌기 → 놓기 → 제자리 · 입력 없음 → 자리비움 → 반기기 · 사용량 네 단계.
그림 팩은 임시 폴더에 직접 만든다(사용자 팩은 안 읽는다). tk 창은 띄우지 않는다(withdraw).
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PC = os.path.dirname(HERE)
sys.path.insert(0, PC)
sys.path.insert(0, os.path.join(PC, "windows"))

import tkinter as tk  # noqa: E402

import pytest  # noqa: E402
from PIL import Image  # noqa: E402

import cooldown_pack as pack  # noqa: E402
from skins import carry  # noqa: E402
from skins.base import AwayWatch, char_mood, set_palette  # noqa: E402
from skins.buddy import RETURN_SEC, TICK_MS, Buddy  # noqa: E402
from skins.claudi import Claudi  # noqa: E402

CHAR = "시험떡"
W, H = 460, 48
BOX = (300, 0, 450, H)


def _png(path, color):
    im = Image.new("RGBA", (20, 24), (0, 0, 0, 0))
    for x in range(3, 17):
        for y in range(4, 24):
            im.putpixel((x, y), color)
    im.save(path)


@pytest.fixture(scope="module")
def packdir():
    d = tempfile.mkdtemp(prefix="cd_pack_")
    for i, motion in enumerate(("서기", "걷기", "놀람", "인사", "끌림", "자리비움")):
        os.makedirs(os.path.join(d, CHAR, motion))
        _png(os.path.join(d, CHAR, motion, "1.png"), (40 * i, 120, 200, 255))
    return d   # 「기절」은 일부러 비워 둔다 (FALLBACK 으로 빌리는지 본다)


@pytest.fixture(scope="module")
def tkroot():
    r = tk.Tk()
    r.withdraw()
    set_palette("dark")
    yield r
    r.destroy()


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def make_buddy(tkroot, packdir):
    c = tk.Canvas(tkroot, width=W, height=H)
    clock = Clock()
    b = Buddy(c, BOX, CHAR, root=packdir)
    b.now = clock
    b._last = clock.t
    b._touched = clock.t
    b._play("서기", 3.0)
    return b, clock


def run(b, clock, seconds):
    for _ in range(int(seconds * 1000 / TICK_MS)):
        clock.t += TICK_MS / 1000
        b.step()


def spot(b):
    """캐릭터 한가운데 (캔버스 좌표)."""
    return b.x, b.y1 + b.y - b.height / 2


# ------------------------------------------------------------------ 팩 동작 이름
def test_new_motion_names():
    for m in ("기절", "끌림", "자리비움"):
        assert m in pack.MOTIONS and pack.MOTION_LABELS[m] and m in pack.FALLBACK


def test_missing_faint_borrows(packdir):
    got = pack.pick(CHAR, "기절", packdir)
    assert got is not None and os.sep + "서기" + os.sep in got  # 잠·눌림도 없으니 서기를 빌린다


# ------------------------------------------------------------------ 사용량 단계
def test_mood_steps():
    assert char_mood(10, 20) == "여유"
    assert char_mood(60, 10) == "보통"
    assert char_mood(10, 85) == "허둥"
    assert char_mood(100, 40) == "잠"
    assert char_mood(None, None) == "여유"


@pytest.fixture
def pressed(monkeypatch):
    """마우스 단추를 누르고 있는 셈 (안 그러면 끄는 중에 놓은 것으로 본다)."""
    monkeypatch.setattr(carry, "button_down", lambda: True)


def test_buddy_drag_inside_bar_walks_home(tkroot, packdir, pressed):
    b, clock = make_buddy(tkroot, packdir)
    home = b.home_x
    x, y = spot(b)
    assert not b.catch(x - 120, y)           # 캐릭터 밖: 끌면 창이 움직인다
    assert b.catch(x, y)
    b.drag(x - 150, y)
    assert b.mode == "끌림" and b.motion == "끌림"
    assert b._carry is not None and b._carry.alive()   # 떠 있는 창에 탔다
    run(b, clock, 1.0)
    assert b.mode == "끌림"                  # 손에 잡혀 있는 동안은 그대로
    b.put_down()                             # 바 위에 놓았다: 그 자리에 내려앉는다
    assert b.mode == "복귀" and b._carry is None
    assert abs(b.x - (home - 150)) < 1
    ticks = 0
    while b.mode == "복귀":                   # 제자리에 닿는 순간 평소로 돌아간다
        clock.t += TICK_MS / 1000
        b.step()
        ticks += 1
        assert ticks * TICK_MS / 1000 <= RETURN_SEC + 0.3
    assert b.x == pytest.approx(home)


def test_buddy_drag_off_screen_flies_home(tkroot, packdir, pressed):
    b, clock = make_buddy(tkroot, packdir)
    home = b.home_x
    x, y = spot(b)
    assert b.catch(x, y)
    b.drag(-900, y - 700)                    # 바 밖 멀리: 가두지 않고 따라간다
    win = b._carry
    sx, sy = carry.screen_of(b.c, -900 + (b.x - x), y - 700 + (b.y1 + b.y - y))
    assert win.at == pytest.approx((sx, sy))
    b._draw()
    assert all(c.itemcget(i, "state") == "hidden" for c, i in b._items.items())  # 바 안 자리는 빈다
    b.put_down()
    assert b.mode == "날기" and b._flight is not None
    run(b, clock, 1.2)                       # 길어도 1.1초면 닿는다
    assert b.mode == "" and b._carry is None and not win.alive()
    assert b.x == pytest.approx(home)
    b._draw()
    assert all(c.itemcget(i, "state") == "normal" for c, i in b._items.items())


def test_buddy_released_elsewhere_lands(tkroot, packdir, monkeypatch):
    """앱이 놓기를 못 받아도(창 전환) 단추가 떨어져 있으면 스스로 내려온다."""
    b, clock = make_buddy(tkroot, packdir)
    x, y = spot(b)
    monkeypatch.setattr(carry, "button_down", lambda: True)
    assert b.catch(x, y)
    b.drag(x, y - 500)
    monkeypatch.setattr(carry, "button_down", lambda: False)
    run(b, clock, 1.2)
    assert b.mode == "" and b._carry is None


def test_buddy_away_and_welcome(tkroot, packdir):
    b, clock = make_buddy(tkroot, packdir)
    idle = [0.0]
    watch = AwayWatch(lambda: idle[0], after=300)
    assert watch.poll() is None
    idle[0] = 299
    assert watch.poll() is None
    idle[0] = 301
    assert watch.poll() is True
    b.x = b.home_x - 60                       # 거닐던 중이었다
    b.set_away(True)
    run(b, clock, 10)
    assert b.mode == "자리비움" and b.motion == "자리비움" and b.x == pytest.approx(b.home_x)
    run(b, clock, 30)
    assert b.mode == "자리비움"                # 돌아올 때까지 그대로
    assert watch.poll() is None
    idle[0] = 0.5
    assert watch.poll() is False
    b.set_away(False)
    assert b.mode == "" and b.motion == "인사"


def test_buddy_mood_shows(tkroot, packdir):
    b, clock = make_buddy(tkroot, packdir)
    b.set_mood("잠")
    b.x = b.home_x + 30
    run(b, clock, 8)
    assert b.x == pytest.approx(b.home_x) and b.motion in ("잠", "서기")  # 잠 그림이 없으면 서기를 빌린다
    b.set_mood("허둥")
    walking = 0
    for _ in range(100):
        clock.t += TICK_MS / 1000
        b.step()
        walking += b.target is not None
    assert walking >= 90                      # 쉬지 않고 오간다


# ------------------------------------------------------------------ 클로디
def frames(cl, n):
    for _ in range(n):
        cl._animate(cl.c, cl._anim_gen)


def make_claudi(tkroot):
    c = tk.Canvas(tkroot, width=W, height=H)
    cl = Claudi(c, (10, 0, 450, H))
    cl.home(330)
    cl.start()
    return cl


def test_claudi_drag_and_return(tkroot, pressed):
    cl = make_claudi(tkroot)
    assert not cl.catch(cl.cx - 80, cl.cy)
    assert cl.catch(cl.cx, cl.cy)
    cl.drag(cl.cx - 200, cl.cy - 10)
    assert cl._grabbed and cl._carry is not None    # 떠 있는 창에 탔다
    frames(cl, 30)
    assert cl._grabbed                        # 잡혀 있는 동안 제자리로 안 돌아간다
    assert not cl.c.find_withtag("mascot") or cl._sparks   # 바 안 자리는 빈다
    cl.put_down()                             # 바 위에 놓았다: 그 자리에서 떨어진다
    assert not cl._grabbed and cl._carry is None
    assert cl._bx == pytest.approx(-200)
    assert cl._yoff == pytest.approx(-10)     # 끌어 올린 높이에서 떨어진다
    frames(cl, 80)
    assert cl._bx == 0.0 and abs(cl._yoff) < 4   # 제자리 (혼자 하는 폴짝은 봐준다)


def test_claudi_drag_off_screen_flies_home(tkroot, pressed):
    cl = make_claudi(tkroot)
    clock = Clock()
    cl.now = clock
    assert cl.catch(cl.cx, cl.cy)
    cl.drag(-999, cl.cy - 600)                # 바 밖 멀리 (가두지 않는다)
    win = cl._carry
    assert win.at == pytest.approx(carry.screen_of(cl.c, -999, cl.cy - 600))
    cl.put_down()
    assert cl._grabbed and cl._flight is not None   # 날아오는 동안은 잡힌 모습 그대로
    for _ in range(30):
        clock.t += 0.045
        frames(cl, 1)
    assert not cl._grabbed and cl._carry is None and not win.alive()
    assert cl._bx == 0.0


def test_claudi_away_naps_until_back(tkroot):
    cl = make_claudi(tkroot)
    frames(cl, 5)
    cl.set_away(True)
    assert cl._act == "nap"
    frames(cl, 700)                           # 딴짓 낮잠(최대 400프레임)보다 길게
    assert cl._act == "nap"
    cl.set_away(False)
    assert cl._act == "" and cl._wave > 0     # 깨어나 손 흔들어 반긴다
    frames(cl, 100)
    assert cl._act != "nap"


def test_claudi_full_limit_naps(tkroot):
    cl = make_claudi(tkroot)
    cl.set_mood("잠")
    frames(cl, 250)                           # 하던 잔동작이 끝나면 곧 존다
    assert cl._act == "nap"
    cl.set_mood("여유")
    assert cl._act == ""
