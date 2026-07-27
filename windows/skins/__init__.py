"""
스킨 목록 — 우클릭 > 디자인 에 이 순서로 뜬다.

새 스킨은 `base.Skin` 을 상속한 클래스 하나를 이 폴더에 두고
아래 `_MODULES` 에 (모듈이름, 클래스이름) 을 추가하면 된다.
한 스킨이 깨져도 나머지는 그대로 뜨도록 개별적으로 불러온다.
"""

from __future__ import annotations

import importlib

from .base import Skin

_MODULES = [
    ("card", "CardSkin"),
    ("arc", "ArcSkin"),
    ("table", "TableSkin"),
    ("slim", "SlimSkin"),
]


def _load() -> list[type[Skin]]:
    found: list[type[Skin]] = []
    for module_name, class_name in _MODULES:
        try:
            module = importlib.import_module(f".{module_name}", __name__)
            found.append(getattr(module, class_name))
        except Exception:  # noqa: BLE001  스킨 하나가 깨져도 앱은 떠야 한다
            continue
    return found


SKINS: list[type[Skin]] = _load()
DEFAULT = "card"


def make(key: str) -> Skin:
    """식별자로 스킨을 만든다. 모르는 값이면 목록의 첫 번째."""
    for cls in SKINS:
        if cls.key == key:
            return cls()
    if not SKINS:
        raise RuntimeError("쓸 수 있는 스킨이 없습니다")
    return SKINS[0]()


__all__ = ["SKINS", "DEFAULT", "Skin", "make"]
