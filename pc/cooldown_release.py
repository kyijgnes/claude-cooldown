"""릴리스를 몇 번 내려받았나 적어 두기 · 옛 릴리스 지우기

★ GitHub 은 **릴리스를 지우면 내려받은 횟수도 같이 지운다.** 옛 판을 손으로 지워 온 탓에
v0.23 이전 숫자는 이제 어디에도 없다. 그래서 **적고 나서 지운다** — 순서를 바꾸면 그 판
숫자가 그대로 사라진다. 지우는 일을 이 도구가 같이 하므로 적는 것을 잊을 수가 없다.

    python pc/cooldown_release.py            지금 숫자를 적고 합계를 보여 준다
    python pc/cooldown_release.py --prune    적은 뒤 최신 판만 남기고 옛 릴리스를 지운다
    python pc/cooldown_release.py --prune --yes   묻지 않고

- 적어 두는 곳은 `~/.claude_cooldown_downloads.json`(집 폴더라 저장소에 안 섞인다).
- 횟수는 **늘기만 한다** — 다시 적을 때 큰 쪽을 남기므로, 지워진 판도 마지막 숫자가 남는다.
- `gh release delete` 는 **git 태그를 건드리지 않는다**(`--cleanup-tag` 를 안 준다).
  어느 커밋이 어느 판인지는 태그가 계속 말해 준다.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # 저장소 뿌리 (pc 의 부모)
STORE = Path.home() / ".claude_cooldown_downloads.json"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _gh(args: list[str]) -> str:
    """gh 를 부르고 표준출력을 돌려준다. 실패하면 stderr 를 그대로 올린다."""
    p = subprocess.run(
        ["gh", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout).strip() or f"gh {args[0]} 실패")
    return p.stdout


def slug() -> str:
    """owner/repo. gh 가 이 폴더의 remote 를 보고 말해 준다."""
    return _gh(["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]).strip()


def fetch(repo: str) -> list[dict]:
    """지금 GitHub 에 있는 릴리스와 자산별 내려받은 횟수.

    판을 하나만 남기는 저장소라 한 쪽(100개)이면 넉넉하다.
    """
    raw = _gh(["api", f"repos/{repo}/releases?per_page=100"])
    out = []
    for r in json.loads(raw):
        out.append(
            {
                "tag": r["tag_name"],
                "published": r.get("published_at") or r.get("created_at"),
                "assets": {a["name"]: int(a["download_count"]) for a in r.get("assets", [])},
            }
        )
    return out


def load() -> dict:
    try:
        return json.loads(STORE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"releases": {}}


def save(data: dict) -> None:
    STORE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def record(data: dict, live: list[dict]) -> dict:
    """지금 숫자를 기록에 얹는다. 횟수는 큰 쪽을 남긴다(내려받기는 늘기만 한다)."""
    now = _now()
    for rel in live:
        slot = data["releases"].setdefault(
            rel["tag"], {"published": rel["published"], "assets": {}, "first_recorded": now}
        )
        slot["published"] = rel["published"] or slot.get("published")
        slot["last_recorded"] = now
        for name, cnt in rel["assets"].items():
            slot["assets"][name] = max(cnt, int(slot["assets"].get(name, 0)))
    return data


def total(slot: dict) -> int:
    return sum(int(v) for v in slot.get("assets", {}).values())


def report(data: dict, live_tags: set[str]) -> None:
    rels = data["releases"]
    if not rels:
        print("적어 둔 판이 없습니다.")
        return

    order = sorted(rels.items(), key=lambda kv: kv[1].get("published") or "", reverse=True)
    print(f"기록: {STORE}")
    print()
    for tag, slot in order:
        mark = "" if tag in live_tags else "  (릴리스는 지움)"
        day = (slot.get("published") or "")[:10]
        print(f"{tag}  {day}  {total(slot)}회{mark}")
        for name, cnt in sorted(slot.get("assets", {}).items()):
            print(f"    {name}  {cnt}")
    print()
    print(f"전체 {sum(total(s) for s in rels.values())}회 · 판 {len(rels)}개")


def prune(repo: str, data: dict, live: list[dict], ask: bool) -> None:
    """최신 판만 남기고 옛 릴리스를 지운다. 태그는 남긴다."""
    if len(live) <= 1:
        print("지울 옛 릴리스가 없습니다.")
        return

    newest = max(live, key=lambda r: r["published"] or "")
    old = [r for r in live if r["tag"] != newest["tag"]]

    print(f"남길 판: {newest['tag']}")
    # 적어 둔 숫자로 말한다 — 지금 조회한 값이 아니라 그게 남을 값이다.
    print("지울 판: " + ", ".join(f"{r['tag']}({total(data['releases'][r['tag']])}회)" for r in old))
    if ask:
        if input("지울까요? [y/N] ").strip().lower() not in ("y", "yes"):
            print("그만둡니다. 숫자는 이미 적어 뒀습니다.")
            return

    for r in old:
        _gh(["release", "delete", r["tag"], "--yes"])
        data["releases"][r["tag"]]["deleted"] = _now()
        print(f"지움: {r['tag']}")
    save(data)


def main(argv: list[str]) -> int:
    do_prune = "--prune" in argv
    ask = "--yes" not in argv

    repo = slug()
    live = fetch(repo)
    data = record(load(), live)
    save(data)

    if do_prune:
        prune(repo, data, live, ask)
        print()
    report(data, {r["tag"] for r in live})
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        raise SystemExit(main(sys.argv[1:]))
    except RuntimeError as e:
        print(f"안 됐습니다: {e}")
        raise SystemExit(1)
