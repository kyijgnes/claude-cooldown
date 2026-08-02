"""
클로드 모닝 스타터 — 자동 핑 로직 (쿨다운 위젯에 통합)
=====================================================
5시간 한도 창은 '첫 메시지 순간'부터 5시간이다. 하루 몇 번, 정해진 앵커
시각(기본 05·10·15·20시)에 토큰을 거의 안 쓰는 핑을 자동으로 보내
5시간 창의 경계를 그 시각들에 맞춰 둔다 — 그래야 언제 초기화되는지 예측이 된다.

이 파일은 **순수 로직만** 담는다 (Tk·트레이 없음). 위젯 본체
(windows/cooldown_app.py)가 이 모듈을 불러 쓴다. 단독 테스트도 된다:

    python cooldown_ping.py           # 지금 쏠지 판단만 출력 (실제 전송 안 함)
    python cooldown_ping.py --send    # 지금 핑 한 번 실제 전송 (창을 연다)

핵심:
- 핑은 **앵커 시각에만** 쏜다. 그 순간 이미 5시간 창이 활성이면
  (resets_at 이 미래) 건너뛴다 — 활성 창에 메시지를 더 보내 봐야 경계가
  밀리지 않고 토큰만 쓴다. 창이 풀린 뒤 다음 앵커에 다시 정렬된다.
- 전송은 브라우저가 아니라 **Claude Code CLI 헤드리스**(`claude -p`)로 한다.
  이미 로그인돼 있고 구독 한도를 공유하므로 5시간 창이 정확히 열린다.
  CLI 는 OAuth 토큰을 스스로 갱신하므로, 위젯의 직접 조회가 401 이어도 핑은 나간다.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, time as dtime, timedelta

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".claude_cooldown_ping.json")
LOG_PATH = os.path.join(os.path.expanduser("~"), ".claude_cooldown_ping.log")
# 핑을 이 폴더에서 실행한다. 큰 프로젝트 CLAUDE.md 를 딸려 읽어 입력 토큰이
# 늘어나는 걸 막으려고 일부러 빈 폴더를 쓴다.
NEUTRAL_CWD = os.path.join(os.path.expanduser("~"), ".claude_cooldown_ping_cwd")

DEFAULT_MODEL = "claude-haiku-4-5-20251001"  # 가장 가벼운 모델 — 주간 한도를 덜 깎는다
# 5시간 창은 정확히 5시간이라, 이전 창이 끝난 '직후'에 다시 시작하도록 1분씩 벌려 둔다.
# (정확히 5시간 간격이면 이전 창이 아직 안 끝난 순간과 겹쳐 새 창이 안 열릴 수 있다)
DEFAULT_TIMES = ["05:00", "10:01", "15:02", "20:03"]
# 출력 토큰을 최소화하려고 한 글자만 답하게 시킨다. 창을 여는 게 목적이라 내용은 무의미.
DEFAULT_PROMPT = "Reply with only the single word: ok"
SEND_TIMEOUT = 120  # 초. CLI 가 이보다 오래 걸리면 실패로 본다.
GRACE_MIN = 5  # 앵커 시각을 이 분(分)만큼 지나쳐도 그 앵커로 인정해 쏜다 (타이머 여유)
MIN_GAP_MIN = 301  # 두 시각 사이 최소 간격(분) = 5시간 1분. 5시간 창이 확실히 지난 뒤 다시 시작.
MAX_TIMES = 4  # 하루 최대 시각 수. 5시간 1분 간격이면 24시간에 4개까지만 들어간다(5×301>1440).

FIVE_WINDOW = timedelta(hours=5)  # 5시간 창 길이 — 놓침 판정에서 '창 안인가'를 볼 때 쓴다

DEFAULTS = {
    "enabled": False,
    "times": list(DEFAULT_TIMES),
    "prompt": DEFAULT_PROMPT,
    "model": DEFAULT_MODEL,
    "last_ping": None,   # ISO(로컬, naive). 같은 앵커에 두 번 쏘지 않게 하는 표시.
    "last_result": "",   # 마지막 전송 결과 (화면 표시용)
    "last_anchor": None, # ISO(로컬). 앱이 떠서 '처리한'(핑·건너뜀·놓침확인) 가장 최근 앵커.
    "last_missed": None, # ISO(로컬). 컴퓨터 꺼짐 등으로 놓친 앵커 (위젯에 표시, 정렬되면 지움).
}


# ---------------------------------------------------------------- 설정


def load_cfg() -> dict:
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            cfg.update(data)
    except (OSError, ValueError):
        pass
    # times 가 깨졌거나 간격 규칙(5시간 1분)을 어기면 기본으로 되돌린다.
    # (예전 05·10·15·20 은 정확히 5시간이라 여기서 05:00·10:01·15:02·20:03 으로 옮겨진다)
    if not parse_times(cfg.get("times")) or gap_error(cfg.get("times")):
        cfg["times"] = list(DEFAULT_TIMES)
    return cfg


def save_cfg(cfg: dict) -> None:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False)
    except OSError:
        pass


def parse_times(items) -> list[dtime]:
    """["05:00", ...] → [time(5,0), ...]. 하나라도 형식이 틀리면 빈 리스트."""
    if not isinstance(items, (list, tuple)) or not items:
        return []
    out: list[dtime] = []
    for s in items:
        try:
            hh, mm = str(s).strip().split(":")
            out.append(dtime(int(hh), int(mm)))
        except (ValueError, AttributeError):
            return []
    return sorted(set(out))


def format_times(items) -> str:
    """time 리스트나 "HH:MM" 리스트를 '05:00, 10:00' 처럼."""
    ts = parse_times(items) if items and isinstance(items[0], str) else items
    return ", ".join(t.strftime("%H:%M") for t in sorted(ts))


def gap_error(items) -> str | None:
    """시각들이 서로 5시간 1분 이상 떨어져 있는지 본다.
    너무 가까운 쌍이 있으면 사람이 읽을 안내 문구를, 없으면 None 을 돌려준다.
    하루는 24시간이라 마지막→처음(자정 넘김)까지 원형으로 검사한다."""
    ts = parse_times(items)
    if len(ts) < 2:
        return None
    mins = sorted(t.hour * 60 + t.minute for t in ts)
    for i, a in enumerate(mins):
        b = mins[(i + 1) % len(mins)]
        gap = (b - a) % 1440 or 1440  # 앞쪽으로의 거리 (원형). 같은 값이면 24시간으로.
        if gap < MIN_GAP_MIN:
            fa = f"{a // 60:02d}:{a % 60:02d}"
            fb = f"{b // 60:02d}:{b % 60:02d}"
            return f"시각 간격은 5시간 1분 이상이어야 해요  ({fa} · {fb})"
    return None


# ---------------------------------------------------------------- 스케줄 판단


def _first_anchor_ge(dt: datetime, times: list[dtime]) -> datetime:
    """dt 이상인 가장 이른 앵커 시각. 오늘에 없으면 내일 첫 앵커."""
    for day in (dt.date(), dt.date() + timedelta(days=1)):
        for t in times:
            cand = datetime.combine(day, t)
            if cand >= dt:
                return cand
    return datetime.combine(dt.date() + timedelta(days=1), times[0])


def should_ping_now(
    now: datetime,
    times: list[dtime],
    resets_at_local: datetime | None,
    last_ping: datetime | None,
    grace_min: int = GRACE_MIN,
) -> bool:
    """지금 핑을 쏴야 하나?

    - 5시간 창이 활성이면(resets_at 이 미래) 안 쏜다.
    - 앵커 시각을 막 지난 여유 구간 안이고, 그 앵커에 아직 안 쐈으면 쏜다.
    """
    if resets_at_local is not None and resets_at_local > now:
        return False
    grace = timedelta(minutes=grace_min)
    for t in times:
        anchor = datetime.combine(now.date(), t)
        if anchor <= now <= anchor + grace and (last_ping is None or last_ping < anchor):
            return True
    return False


def predict_next(
    now: datetime, times: list[dtime], resets_at_local: datetime | None
) -> datetime:
    """다음에 핑이 (시도)될 시각. 화면에 '다음 핑 10:00' 으로 보여 주기 위한 것."""
    floor = resets_at_local if (resets_at_local and resets_at_local > now) else now
    return _first_anchor_ge(floor, times)


# ---------------------------------------------------------------- 놓친 앵커 판정
# 컴퓨터가 꺼져 있던 등으로 앱이 떠 있지 않은 동안 앵커 시각이 다 지나가 버리면
# 그 앵커는 핑도 못 쏘고 '처리함'(last_anchor) 기록도 못 남긴다 — 그게 '놓침' 이다.
# 앱이 떠 있었으면 그 앵커는 핑을 쏘거나(창 비었으면) 창이 활성이라 건너뛰며,
# 어느 쪽이든 위젯이 last_anchor 에 기록해 둔다.


def anchor_in_grace(
    now: datetime, times: list[dtime], grace_min: int = GRACE_MIN
) -> datetime | None:
    """지금이 어떤 앵커의 여유(grace) 구간 안이면 그 앵커, 아니면 None.

    should_ping_now 과 달리 창 상태·last_ping 과 무관하다 — 앱이 이 앵커를 '지금
    처리 중'(그 자리에 떠 있음)인지만 본다. 이 구간에 떠 있었으면 놓친 게 아니다.
    """
    grace = timedelta(minutes=grace_min)
    for t in times:
        anchor = datetime.combine(now.date(), t)
        if anchor <= now <= anchor + grace:
            return anchor
    return None


def last_due_anchor(
    now: datetime, times: list[dtime], grace_min: int = GRACE_MIN
) -> datetime | None:
    """now 기준, 여유(grace)까지 완전히 지나간 가장 최근 앵커. 없으면 None.
    자정을 넘겨 어제 마지막 앵커가 가장 최근일 수 있어 어제까지 본다."""
    if not times:
        return None
    grace = timedelta(minutes=grace_min)
    best: datetime | None = None
    for day in (now.date(), now.date() - timedelta(days=1)):
        for t in times:
            anchor = datetime.combine(day, t)
            if anchor + grace < now and (best is None or anchor > best):
                best = anchor
    return best


def missed_since(
    now: datetime,
    times: list[dtime],
    resets_at_local: datetime | None,
    last_ping: datetime | None,
    last_anchor: datetime | None,
    grace_min: int = GRACE_MIN,
) -> datetime | None:
    """지나쳐 '놓친' 가장 최근 앵커. 없으면 None.

    - last_anchor 이하면 앱이 떠서 이미 처리(또는 놓침 확인)한 앵커다.
    - last_ping 이 그 앵커 즈음/이후면 이미 쐈다.
    - 그 앵커가 지금 활성인 5시간 창 안에 들어 있으면 의도적 건너뜀이라 놓친 게 아니다
      (창이 그 앵커를 이미 덮고 있으니 경계는 어차피 안 밀린다).
    """
    anchor = last_due_anchor(now, times, grace_min)
    if anchor is None:
        return None
    if last_anchor is not None and last_anchor >= anchor:
        return None
    if last_ping is not None and last_ping >= anchor:
        return None
    if resets_at_local is not None and resets_at_local > now:
        start = resets_at_local - FIVE_WINDOW
        if start <= anchor <= resets_at_local:
            return None
    return anchor


# ---------------------------------------------------------------- 전송


def find_claude() -> str | None:
    """claude CLI 실행 파일 경로. npm 전역 설치면 .cmd 배치 파일이다."""
    for name in ("claude.cmd", "claude.exe", "claude"):
        found = shutil.which(name)
        if found:
            return found
    appdata = os.environ.get("APPDATA", "")
    for cand in (
        os.path.join(appdata, "npm", "claude.cmd"),
        os.path.join(os.path.expanduser("~"), ".local", "bin", "claude.exe"),
    ):
        if os.path.exists(cand):
            return cand
    return None


def _q(s: str) -> str:
    """cmd.exe 인자용 따옴표 감싸기. 안의 큰따옴표는 두 개로 이스케이프."""
    return '"' + str(s).replace('"', '""') + '"'


def _log(line: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        # 로그가 무한정 커지지 않게 마지막 ~200줄만 남긴다
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
    """실패 원인(개발자용 원문)을 화면에 보일 한국어 명사형으로 바꾼다.
    원문(영문 stderr·'오류 코드 N' 등)은 로그 파일에만 남기고, 사용자에겐 이걸 보여 준다."""
    s = str(raw or "")
    low = s.lower()
    if "claude" in low and ("없" in s or "찾" in s or "not found" in low):
        return "클로드 코드가 없어요 (설치·로그인 확인)"
    if "시간 초과" in s or "timeout" in low or "timed out" in low:
        return "시간이 초과됐어요"
    return "실행 실패 (잠시 후 다시)"


def read_log_entries(limit: int = 40) -> list[tuple[datetime, bool, str]]:
    """핑 로그를 (시각, 성공?, 상세) 리스트로 돌려준다. 오래된 것이 앞.
    화면(핑 기록)이 사람이 읽기 좋게 다시 꾸미도록 파싱만 해 준다."""
    out: list[tuple[datetime, bool, str]] = []
    if not os.path.exists(LOG_PATH):
        return out
    try:
        with open(LOG_PATH, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        return out
    for line in lines[-limit:]:
        if not line.startswith("["):
            continue
        try:
            stamp, rest = line[1:].split("] ", 1)
            when = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S")
        except (ValueError, IndexError):
            continue
        ok = rest.startswith("성공")
        detail = rest.split(":", 1)[1].strip() if ":" in rest else rest.strip()
        out.append((when, ok, detail))
    return out


def send_ping(cfg: dict) -> tuple[bool, str]:
    """핑 한 번 전송. (성공?, 짧은 결과 문구) 를 돌려준다. 블로킹이므로
    위젯에서는 별도 스레드에서 부를 것."""
    claude = find_claude()
    if not claude:
        _log("실패: claude 실행 파일을 찾지 못함")
        return False, "claude 없음"

    prompt = cfg.get("prompt") or DEFAULT_PROMPT
    model = cfg.get("model") or DEFAULT_MODEL
    try:
        os.makedirs(NEUTRAL_CWD, exist_ok=True)
    except OSError:
        pass

    cmd = f"{_q(claude)} -p {_q(prompt)} --max-turns 1 --model {model}"
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # 콘솔 창 안 뜨게 (Windows)
    try:
        r = subprocess.run(
            cmd,
            shell=True,
            cwd=NEUTRAL_CWD if os.path.isdir(NEUTRAL_CWD) else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=int(cfg.get("timeout", SEND_TIMEOUT)),
            creationflags=flags,
        )
    except subprocess.TimeoutExpired:
        _log("실패: 시간 초과")
        return False, "시간 초과"
    except Exception as e:  # noqa: BLE001
        _log(f"실패: {e}")
        return False, str(e)[:60]

    if r.returncode == 0:
        out = " ".join((r.stdout or "").split())[:40] or "완료"
        _log(f"성공: {out}")
        return True, out

    tail = " ".join((r.stderr or r.stdout or "").split())[:80]
    _log(f"실패(코드 {r.returncode}): {tail}")
    return False, tail or f"오류 코드 {r.returncode}"


# ---------------------------------------------------------------- 단독 실행


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _parse_iso(s) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


if __name__ == "__main__":
    cfg = load_cfg()
    times = parse_times(cfg["times"])
    now = datetime.now()
    last = _parse_iso(cfg.get("last_ping"))

    if "--send" in sys.argv:
        # 수동 전송이므로 앵커 정렬용 last_ping 은 건드리지 않는다 (GUI 와 동일).
        ok, detail = send_ping(cfg)
        cfg["last_result"] = ("성공: " if ok else "실패: ") + detail
        save_cfg(cfg)
        print(("전송 성공 — " if ok else "전송 실패 — ") + detail)
        sys.exit(0 if ok else 1)

    print(f"자동 핑: {'켜짐' if cfg['enabled'] else '꺼짐'}")
    print(f"앵커 시각: {format_times(times)}")
    print(f"지금({now:%H:%M}) 쏠까? {should_ping_now(now, times, None, last)}")
    print(f"다음 핑 예정: {predict_next(now, times, None):%m-%d %H:%M}")
    print(f"마지막 결과: {cfg.get('last_result') or '-'}")
