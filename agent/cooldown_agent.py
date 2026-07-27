"""
클로드 쿨다운 에이전트 (폰 위젯용)
====================================
이 PC 의 Claude 구독 사용률(5시간 / 주간)을 5분마다 읽어서
지정된 주소로 '퍼센트 숫자만' 올립니다.

★ 로그인 토큰은 이 PC 밖으로 절대 나가지 않습니다.
  (~/.claude/.credentials.json 은 읽기만 하고, 전송하지 않습니다)

설치:  pip install requests
실행:  pythonw cooldown_agent.py
키 확인:  python cooldown_agent.py --info

바탕화면 위젯만 쓸 거면 이 파일은 필요 없습니다 — desktop/cooldown_app.py 만 실행하세요.
"""

from __future__ import annotations

import json
import os
import secrets
import sys
import time
from datetime import datetime

import requests

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "desktop"),
)
from cooldown_core import MIN_INTERVAL, LoginRequired, UsageError, fetch  # noqa: E402

# ─── 배포 시 여기만 본인 서버 주소로 바꿔서 나눠주면 됩니다 ───
PUSH_URL = os.environ.get("CU_PUSH_URL", "https://내앱.vercel.app/api/cooldown")
# ─────────────────────────────────────────────────────────────

HOME = os.path.expanduser("~")
CONF_PATH = os.path.join(HOME, ".claude_cooldown_agent.json")
LOCAL_PATH = os.path.join(HOME, ".claude_cooldown.json")  # 데스크탑 위젯과 공용


def load_conf() -> dict:
    try:
        with open(CONF_PATH, encoding="utf-8") as f:
            conf = json.load(f)
        if conf.get("key"):
            return conf
    except (OSError, ValueError):
        pass
    conf = {"key": secrets.token_hex(16)}
    with open(CONF_PATH, "w", encoding="utf-8") as f:
        json.dump(conf, f)
    return conf


def main() -> None:
    conf = load_conf()
    widget_url = f"{PUSH_URL}?key={conf['key']}"

    if "--info" in sys.argv:
        print("내 키   :", conf["key"])
        print("위젯 주소:", widget_url)
        print("\nKWGT 수식:")
        print(f'$wg("{widget_url}", json, .five_hour_pct)$%')
        return

    print("위젯 주소:", widget_url)
    print("이 주소를 KWGT 수식에 넣으세요. (키는 남에게 공유하지 마세요)")

    while True:
        stamp = datetime.now().strftime("%H:%M")
        try:
            data = fetch().as_dict()
            with open(LOCAL_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            requests.post(
                PUSH_URL, json={**data, "key": conf["key"]}, timeout=15
            )
            print(stamp, f"5시간 {data['five_hour_pct']}%  주간 {data['seven_day_pct']}%")
        except LoginRequired as e:
            print(stamp, "재로그인 필요:", e)
        except (UsageError, requests.RequestException) as e:
            print(stamp, "실패:", e)
        time.sleep(MIN_INTERVAL)


if __name__ == "__main__":
    main()
