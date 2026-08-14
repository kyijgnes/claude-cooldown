"""
클로드 쿨다운 — 폰으로 보내기 (릴레이 업로드)
================================================
이 PC 가 조회한 사용률을 **퍼센트와 초기화 시각만** 릴레이 서버에 올린다.
폰 앱은 그 서버에서 읽어 간다.

★ 토큰(accessToken/refreshToken)은 절대 나가지 않는다 — Usage.as_dict() 만 보낸다.

- 설정 파일: ~/.claude_cooldown_push.json  {enabled, url, key, last_ok}
- key 는 32 hex. 서버의 읽기 비밀번호 역할이라 남에게 주면 안 된다.
- 단독 확인: python cooldown_push.py          (지금 설정·주소 보기)
             python cooldown_push.py --send   (실제로 한 번 올리기)
"""

from __future__ import annotations

import json
import os
import re
import secrets
from datetime import datetime
from urllib.parse import quote, urlparse

import requests

from cooldown_core import Usage

HOME = os.path.expanduser("~")
CFG_PATH = os.path.join(HOME, ".claude_cooldown_push.json")

PATH = "/api/cooldown"  # 서버 라우트. server/app/api/cooldown/route.ts 와 같아야 한다.
KEY_RE = re.compile(r"^[0-9a-f]{32}$")  # route.ts 의 VALID_KEY 와 같은 규칙
TIMEOUT = 15

# 폰 앱이 QR 로 읽는 주소. 안드로이드 앱의 intent-filter 와 같아야 한다.
PAIR_SCHEME = "claudecooldown"


class PushError(Exception):
    """폰으로 못 보냈다. 문구는 짧은 명사형으로 — 화면에 그대로 나간다."""


# ---------------------------------------------------------------- 설정


def new_key() -> str:
    return secrets.token_hex(16)


def load_cfg() -> dict:
    """설정을 읽는다. 키가 없으면 만들어 저장한다."""
    cfg = {"enabled": False, "url": "", "key": "", "last_ok": ""}
    try:
        with open(CFG_PATH, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass

    if not KEY_RE.match(str(cfg.get("key") or "")):
        cfg["key"] = new_key()
        save_cfg(cfg)
    cfg["url"] = normalize_url(cfg.get("url"))
    return cfg


def save_cfg(cfg: dict) -> None:
    try:
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False)
    except OSError:
        pass


def normalize_url(raw) -> str:
    """사용자가 붙여넣은 주소를 **서버 주소(끝에 /api/cooldown 없이)** 로 정돈한다.

    'myapp.vercel.app', 'https://myapp.vercel.app/', 'https://myapp.vercel.app/api/cooldown'
    셋 다 같은 값이 된다. 알아볼 수 없으면 빈 문자열.
    """
    text = str(raw or "").strip().rstrip("/")
    if not text:
        return ""
    if "://" not in text:
        text = "https://" + text
    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return ""
    path = parsed.path.rstrip("/")
    if path.endswith(PATH):
        path = path[: -len(PATH)]
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def endpoint(cfg: dict) -> str:
    base = normalize_url(cfg.get("url"))
    return base + PATH if base else ""


def read_url(cfg: dict) -> str:
    """폰이 읽어가는 주소 (브라우저에 붙여넣어 확인할 때도 쓴다)."""
    ep = endpoint(cfg)
    return f"{ep}?key={cfg['key']}" if ep else ""


def pair_uri(cfg: dict) -> str:
    """QR 에 담는 값. 폰 앱이 이걸 읽으면 주소·키가 한 번에 들어간다."""
    base = normalize_url(cfg.get("url"))
    if not base:
        return ""
    return f"{PAIR_SCHEME}://pair?url={quote(base, safe='')}&key={cfg['key']}"


def ready(cfg: dict) -> bool:
    """지금 보낼 수 있는 상태인가."""
    return bool(cfg.get("enabled")) and bool(endpoint(cfg)) and bool(cfg.get("key"))


# ---------------------------------------------------------------- 전송


def push(usage: Usage, cfg: dict) -> dict:
    """퍼센트만 올린다. 실패하면 PushError.

    **응답을 돌려준다** — 서버가 원격 대기의 '원하는 상태(want)' 를 얹어 주기 때문이다.
    그 덕에 PC 가 그것 하나 때문에 2분마다 따로 물어보지 않아도 된다(무료 한도 절약).
    """
    url = endpoint(cfg)
    if not url:
        raise PushError("주소 없음")

    body = usage.as_dict()  # five_hour_pct / five_hour_reset / seven_day_* / updated_at
    body["key"] = cfg["key"]

    try:
        r = requests.post(url, json=body, timeout=TIMEOUT)
    except requests.Timeout as e:
        raise PushError("응답 없음") from e
    except requests.RequestException as e:
        raise PushError("연결 실패") from e

    if r.status_code == 400:
        raise PushError("키 오류")
    if r.status_code == 404:
        raise PushError("주소 오류")
    if r.status_code >= 400:
        raise PushError(f"서버 오류 {r.status_code}")

    cfg["last_ok"] = datetime.now().isoformat(timespec="seconds")
    save_cfg(cfg)
    try:
        data = r.json()
    except ValueError:  # 옛 서버는 {ok:true} 만 준다 — 그래도 올리기는 성공이다
        return {}
    return data if isinstance(data, dict) else {}


def last_ok_at(cfg: dict) -> datetime | None:
    try:
        return datetime.fromisoformat(str(cfg.get("last_ok") or ""))
    except ValueError:
        return None


# ---------------------------------------------------------------- QR


def qr_image(text: str, box: int = 5, border: int = 2):
    """QR 을 PIL 이미지로. qrcode 가 없으면 None (그때는 주소를 글자로 보여 준다).

    어두운 테마에서도 폰 카메라가 읽어야 하므로 QR 자체는 늘 흰 바탕·검은 칸이다.
    """
    if not text:
        return None
    try:
        import qrcode
    except ImportError:
        return None
    try:
        qr = qrcode.QRCode(box_size=box, border=border)
        qr.add_data(text)
        qr.make(fit=True)
        return qr.make_image(fill_color="black", back_color="white").convert("RGB")
    except Exception:  # noqa: BLE001  qrcode 내부 오류까지 앱을 죽이지 않는다
        return None


# ---------------------------------------------------------------- 단독 실행


def main() -> int:
    import sys

    from cooldown_core import fetch

    cfg = load_cfg()
    print("주소   :", endpoint(cfg) or "(설정 안 됨)")
    print("키     :", cfg["key"])
    print("보내기 :", "켜짐" if cfg.get("enabled") else "꺼짐")
    print("마지막 :", cfg.get("last_ok") or "없음")
    print("폰 QR  :", pair_uri(cfg) or "(주소부터 설정)")

    if "--send" not in sys.argv:
        return 0

    try:
        push(fetch(), cfg)
    except Exception as e:  # noqa: BLE001
        print("실패:", e)
        return 1
    print("보냄. 확인:", read_url(cfg))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
