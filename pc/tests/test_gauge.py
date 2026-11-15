"""게이지 채움·눈금(`skins.base.seg_fills`·`fill_w`·`cooldown_core.marks`)과
클로드 코드 찾기(`cooldown_ping.claude_usable`) 단위 테스트. 화면·tk 없이 돈다."""
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
WIN = os.path.join(os.path.dirname(HERE), "windows")
sys.path.insert(0, WIN)
sys.path.insert(0, os.path.dirname(WIN))

import cooldown_ping  # noqa: E402
from cooldown_core import Limit, Usage, five_due, marks, pace  # noqa: E402
from skins.base import fill_w, mark_x, seg_fills  # noqa: E402


def _usage(five, week, five_left_h=2.0, week_left_d=3.0, now=None):
    now = now or datetime.now(timezone.utc)
    return Usage(
        five=Limit("5시간", five, now + timedelta(hours=five_left_h)),
        week=Limit("주간", week, now + timedelta(days=week_left_d)),
        scoped=[],
        fetched_at=now,
    )


def _edge(fills, pitch):
    """칸 게이지에서 채움이 끝난 x."""
    last = max((i for i, w in enumerate(fills) if w > 0), default=None)
    return 0.0 if last is None else last * pitch + fills[last]


def test_partial_segment_matches_continuous_fill():
    # 10칸 · 칸 사이 틈 없음: 57% 는 57% 자리에서 끝나야 한다 (옛날엔 50% 에서 끝났다)
    pitch = 10.0
    fills = seg_fills(57, 10, pitch, pitch)
    assert abs(_edge(fills, pitch) - fill_w(57, 100)) < 1e-9


def test_used_equals_due_meets_mark():
    pitch = 8.0
    fills = seg_fills(42.5, 10, pitch, pitch)
    assert abs(_edge(fills, pitch) - mark_x(42.5, 80)) < 1e-9


def test_full_only_at_100():
    pitch, seg_w = 8.0, 6.0
    assert seg_fills(100, 10, pitch, seg_w)[-1] == seg_w
    assert seg_fills(99.9, 10, pitch, seg_w)[-1] < seg_w


def test_tiny_value_still_visible():
    assert seg_fills(0.3, 10, 8.0, 6.0)[0] >= 2.0
    assert seg_fills(0, 10, 8.0, 6.0) == [0.0] * 10
    assert seg_fills(None, 10, 8.0, 6.0) == [0.0] * 10


def test_marks_same_as_pace_and_five_due():
    now = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
    u = _usage(30, 55, now=now)
    m = marks(u, now)
    assert m.five == five_due(u, now)
    assert m.week_due == pace(u, now).due


def test_broken_npm_shim_is_skipped():
    with tempfile.TemporaryDirectory() as d:
        shim = os.path.join(d, "claude.cmd")
        open(shim, "w").close()
        os.makedirs(os.path.join(d, "node_modules"))
        assert not cooldown_ping.claude_usable(shim)  # 꾸러미가 지워진 껍데기
        os.makedirs(os.path.join(d, "node_modules", "@anthropic-ai", "claude-code"))
        open(os.path.join(d, "node.exe"), "w").close()
        assert cooldown_ping.claude_usable(shim)
    assert not cooldown_ping.claude_usable(os.path.join(tempfile.gettempdir(), "없는", "claude.exe"))
