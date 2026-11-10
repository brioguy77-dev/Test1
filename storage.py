"""쇼핑 리스트 데이터를 JSON 파일로 읽고 쓰는 모듈.

여러 탭·기기(= 여러 Streamlit 세션)가 같은 파일을 공유하므로, 변경은 반드시
update_items()로 "최신 파일 읽기 → 변경 → 저장"을 잠금 안에서 한 번에 처리한다.
세션에 보관한 오래된 목록으로 파일을 덮어쓰면 다른 세션의 변경이 사라진다.
"""

import json
import os
import tempfile
import threading
import uuid
from collections.abc import Callable
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_FILE = DATA_DIR / "shopping_list.json"

# Streamlit 세션들은 같은 프로세스의 스레드로 실행되므로 스레드 잠금으로 충분하다.
_lock = threading.RLock()


def _normalize(raw: object, seen_ids: set[str]) -> dict | None:
    """저장된 항목 하나를 PRD 데이터 모델에 맞게 보정한다. 복구할 수 없으면 None."""
    if not isinstance(raw, dict):
        return None
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    try:
        quantity = max(int(raw.get("quantity", 1)), 1)
    except (TypeError, ValueError):
        quantity = 1
    item_id = raw.get("id")
    if not isinstance(item_id, str) or not item_id or item_id in seen_ids:
        item_id = str(uuid.uuid4())
    seen_ids.add(item_id)
    created_at = raw.get("created_at")
    return {
        "id": item_id,
        "name": name.strip(),
        "quantity": quantity,
        "checked": raw.get("checked") is True,
        "created_at": created_at if isinstance(created_at, str) else "",
    }


def _quarantine_corrupt_file() -> None:
    """읽을 수 없는 파일을 지우지 않고 옆에 보관해 둔다 (다음 저장 때 덮어쓰지 않도록)."""
    backup = DATA_FILE.with_name(DATA_FILE.stem + ".corrupt.json")
    try:
        os.replace(DATA_FILE, backup)
    except OSError:
        pass


def load_items() -> list[dict]:
    """저장된 아이템 목록을 읽는다.

    파일이 없거나 손상됐으면 빈 리스트를 반환하고, 형식이 잘못된 항목은 보정하거나 건너뛴다.
    """
    with _lock:
        try:
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except (json.JSONDecodeError, UnicodeDecodeError):
            _quarantine_corrupt_file()
            return []
        except OSError:
            return []
    if not isinstance(data, list):
        return []
    seen_ids: set[str] = set()
    return [item for raw in data if (item := _normalize(raw, seen_ids)) is not None]


def save_items(items: list[dict]) -> None:
    """아이템 목록을 JSON 파일로 저장한다.

    임시 파일에 쓴 뒤 교체하므로 저장 도중 중단돼도 기존 파일이 깨지지 않는다.
    """
    with _lock:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=DATA_DIR, prefix=".tmp-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, DATA_FILE)
        except BaseException:
            Path(tmp_path).unlink(missing_ok=True)
            raise


def update_items(change: Callable[[list[dict]], list[dict]]) -> list[dict]:
    """최신 목록에 change를 적용해 저장하고 결과를 반환한다.

    change가 ValueError를 발생시키면 저장하지 않고 그대로 전달한다.
    """
    with _lock:
        new_items = change(load_items())
        save_items(new_items)
        return new_items
