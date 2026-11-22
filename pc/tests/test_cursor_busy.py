"""
커서 상호작용(쳐다보기·갸웃·간지럼)이 캐릭터가 **무언가 하는 중**에도 나오나 (11-22 v0.62 고침).

v0.62 에서 실제 바에서는 하나도 안 나왔는데 시험은 통과했다. 옛 시험은 모두 `b.until` 을 늘려
캐릭터를 세워 둔 채 커서를 한 점에 딱 고정했다. 실제로는 캐릭터가 거닐고(`target`), 딴짓을 하고,
막 다음 동작을 고른 참이며, 커서는 몇 px 씩 떨린다. 거닐던 캐릭터가 멈추지 않으면 커서에서
멀어져 `WATCH_LOOK`·`HOVER_SEC` 를 못 채운다. 여기서는 그 세 경우를 떨리는 커서로 본다.
"""

from __future__ import annotations

import os
import random
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "windows"))

from test_interact_one import (  # noqa: E402
    BASE, calm_world, make, make_pack, run, screen_mid, seen, tkroot,  # noqa: F401
)

from skins import buddy as buddy_mod  # noqa: E402
from skins.buddy import HOVER_SEC, RUB_WINDOW, WATCH_LOOK  # noqa: E402


@pytest.fixture
def base(tmp_path):
    return make_pack(str(tmp_path), BASE)


def shaky(at, amp=3, seed=7):
    """`at()` 자리에서 몇 px 씩 떨리는 커서 (손이 마우스 위에 있으면 늘 조금 움직인다)."""
    rnd = random.Random(seed)

    def pos():
        x, y = at()
        return x + rnd.randint(-amp, amp), y + rnd.randint(-amp, amp)
    return pos


def walking(b):
    """바 왼쪽 끝에서 오른쪽 끝으로 거니는 중."""
    lo, hi = b._bounds()
    b.x = lo + 4
    b.target = hi
    b.until = 0
    b.busy = False
    assert b.mode == "" and b.target is not None


def doing_idle(b):
    """딴짓 그림 하나를 트는 중 (평소 동작, busy)."""
    b._show("딴짓", 3.0)
    assert b.motion == "딴짓" and b.busy


def just_chose(b, monkeypatch):
    """평소 그림이 막 끝나 이번 틱에 `_choose` 가 거닐기를 고른다."""
    monkeypatch.setattr(buddy_mod.random, "random", lambda: 0.55)
    lo, _ = b._bounds()
    b.x = b.home_x = lo + 4
    b.until = 0
    b.busy = False


SETUPS = ("걷기", "딴짓", "막 고름")


def prepare(b, how, monkeypatch):
    if how == "걷기":
        walking(b)
    elif how == "딴짓":
        doing_idle(b)
    else:
        just_chose(b, monkeypatch)


@pytest.mark.parametrize("how", SETUPS)
def test_look_while_busy(tkroot, base, monkeypatch, how):
    b, clock = make(tkroot, base)
    prepare(b, how, monkeypatch)
    cx, cy = screen_mid(b)
    b.pointer = shaky(lambda: (cx + 40, cy))               # 옆에 둔 커서 (그 자리에 그대로)
    got = seen(b, clock, WATCH_LOOK + 0.4)
    assert b.motion == "쳐다보기" and b.mode == "봄", got
    assert abs(b.x - (cx - b.c.winfo_rootx())) <= 2        # 거닐던 것은 그 자리에 멈췄다
    assert got.count("쳐다보기") == 1 and got[-1] == "쳐다보기"


@pytest.mark.parametrize("how", SETUPS)
def test_stops_in_place_with_same_picture(tkroot, base, monkeypatch, how):
    b, clock = make(tkroot, base)
    prepare(b, how, monkeypatch)
    cx, cy = screen_mid(b)
    b.pointer = shaky(lambda: (cx + 40, cy))
    run(b, clock, 0.04)               # 커서가 온 첫 틱 (막 고른 경우는 이 틱에 거닐기를 골라 한 걸음 뗀다)
    first, x0 = b.motion, b.x
    got = seen(b, clock, WATCH_LOOK - 0.3)
    assert got == [first]                                   # 정하는 동안 새 그림을 고르지 않는다
    assert abs(b.x - x0) <= 1 and b.target is None         # 그 자리에 멈춰 섰다


@pytest.mark.parametrize("how", SETUPS)
def test_tilt_while_busy(tkroot, base, monkeypatch, how):
    b, clock = make(tkroot, base)
    prepare(b, how, monkeypatch)
    cx, cy = screen_mid(b)
    b.pointer = shaky(lambda: (cx + 1, cy))                # 몸 위에 둔 손 (몇 px 씩 떨림)
    got = seen(b, clock, HOVER_SEC + 0.4)
    assert got[-1] == "갸웃", got
    assert "쳐다보기" in got                                # 2초에 쳐다보기, 4초에 갸웃으로 오른다


@pytest.mark.parametrize("how", SETUPS)
def test_rub_while_busy(tkroot, base, monkeypatch, how):
    b, clock = make(tkroot, base)
    prepare(b, how, monkeypatch)
    cx, cy = screen_mid(b)
    side = {"d": -8}
    b.pointer = shaky(lambda: (cx + side["d"], cy), amp=1)
    for _ in range(9):
        side["d"] = -side["d"]
        run(b, clock, 0.12)
    assert b.motion == "간지럼" and b.mode == "봄"
    assert RUB_WINDOW > 0.6


@pytest.mark.parametrize("how", SETUPS)
def test_back_to_normal_after_cursor_leaves(tkroot, base, monkeypatch, how):
    b, clock = make(tkroot, base)
    prepare(b, how, monkeypatch)
    cx, cy = screen_mid(b)
    pos = {"far": False}
    near = shaky(lambda: (cx + 40, cy))
    b.pointer = lambda: (cx + 900, cy) if pos["far"] else near()
    run(b, clock, WATCH_LOOK + 0.4)
    assert b.motion == "쳐다보기"
    pos["far"] = True
    run(b, clock, 0.2)
    assert b.mode == "" and b.motion != "쳐다보기"
    monkeypatch.setattr(buddy_mod.random, "random", random.Random(3).random)
    x0 = b.x
    got = seen(b, clock, 30.0)
    assert len(got) > 1 or abs(b.x - x0) > 5               # 다시 평소처럼 거닐거나 다른 그림을 튼다
