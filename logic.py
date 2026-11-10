"""쇼핑 리스트 CRUD 및 검증 로직 (Streamlit과 무관한 순수 함수).

모든 함수는 입력 리스트를 변경하지 않고 새 리스트를 반환한다.
검증 실패 시 사용자에게 보여줄 메시지와 함께 ValueError를 발생시킨다.
"""

import re
import uuid
from datetime import datetime

MAX_NAME_LENGTH = 50
MIN_QUANTITY = 1

# str.strip()이 제거하지 않는 폭 없는 문자 (zero-width space/non-joiner/joiner, BOM)
_INVISIBLE_CHARS = re.compile("[​‌‍⁠﻿]")
# Streamlit Markdown에서 서식으로 해석될 수 있는 문자 (CommonMark는 모든 ASCII 구두점 이스케이프 허용)
_MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+\-.!|~<>$:=])")


def normalize_name(name: str) -> str:
    """폭 없는 문자를 지우고 앞뒤 공백을 제거한 이름을 반환한다."""
    return _INVISIBLE_CHARS.sub("", name or "").strip()


def escape_markdown(text: str) -> str:
    """사용자 입력이 st.toast/st.warning 등에서 Markdown 서식으로 해석되지 않게 이스케이프한다."""
    return _MARKDOWN_SPECIAL.sub(r"\\\1", text)


def shorten(text: str, limit: int = 20) -> str:
    """알림 메시지용으로 긴 이름을 줄인다."""
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _name_key(name: str) -> str:
    """중복 비교용 키 (앞뒤 공백 제거 + 대소문자 무시)."""
    return normalize_name(name).casefold()


def validate_name(items: list[dict], name: str, exclude_id: str | None = None) -> str:
    """이름을 검증하고 정규화된 이름을 반환한다.

    exclude_id에 해당하는 아이템(수정 중인 자기 자신)은 중복 검사에서 제외한다.
    """
    cleaned = normalize_name(name)
    if not cleaned:
        raise ValueError("아이템 이름을 입력해 주세요.")
    if len(cleaned) > MAX_NAME_LENGTH:
        raise ValueError(f"아이템 이름은 {MAX_NAME_LENGTH}자 이하로 입력해 주세요.")
    key = cleaned.casefold()
    for item in items:
        if item["id"] != exclude_id and _name_key(item["name"]) == key:
            raise ValueError(f"'{cleaned}'은(는) 이미 목록에 있어요.")
    return cleaned


def validate_quantity(quantity: int) -> int:
    """수량을 검증하고 정수로 반환한다."""
    try:
        qty = int(quantity)
    except (TypeError, ValueError):
        raise ValueError("수량은 숫자로 입력해 주세요.") from None
    if qty < MIN_QUANTITY:
        raise ValueError(f"수량은 {MIN_QUANTITY} 이상이어야 해요.")
    return qty


def add_item(items: list[dict], name: str, quantity: int = 1) -> list[dict]:
    """새 아이템을 추가한 목록을 반환한다."""
    new_item = {
        "id": str(uuid.uuid4()),
        "name": validate_name(items, name),
        "quantity": validate_quantity(quantity),
        "checked": False,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    return [*items, new_item]


def _require(items: list[dict], item_id: str) -> None:
    """id에 해당하는 아이템이 없으면 ValueError를 발생시킨다."""
    if not any(item["id"] == item_id for item in items):
        raise ValueError("해당 아이템을 찾을 수 없어요.")


def update_item(items: list[dict], item_id: str, name: str, quantity: int) -> list[dict]:
    """id로 찾은 아이템의 이름과 수량을 수정한 목록을 반환한다."""
    _require(items, item_id)
    cleaned = validate_name(items, name, exclude_id=item_id)
    qty = validate_quantity(quantity)
    return [
        {**item, "name": cleaned, "quantity": qty} if item["id"] == item_id else item
        for item in items
    ]


def delete_item(items: list[dict], item_id: str) -> list[dict]:
    """id로 찾은 아이템을 삭제한 목록을 반환한다."""
    return [item for item in items if item["id"] != item_id]


def set_checked(items: list[dict], item_id: str, checked: bool) -> list[dict]:
    """id로 찾은 아이템의 체크 상태를 지정한 목록을 반환한다."""
    return [
        {**item, "checked": bool(checked)} if item["id"] == item_id else item
        for item in items
    ]


def clear_checked(items: list[dict]) -> list[dict]:
    """체크된 아이템을 모두 제거한 목록을 반환한다."""
    return [item for item in items if not item["checked"]]


def sorted_for_display(items: list[dict]) -> list[dict]:
    """미체크 아이템을 위로, 체크된 아이템을 아래로 정렬한다 (각 그룹 내 순서 유지)."""
    return sorted(items, key=lambda item: item["checked"])


def progress(items: list[dict]) -> tuple[int, int]:
    """(체크된 개수, 전체 개수)를 반환한다."""
    return sum(1 for item in items if item["checked"]), len(items)
