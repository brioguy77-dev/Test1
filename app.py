"""쇼핑 리스트 Streamlit 앱."""

import html
from collections.abc import Callable

import streamlit as st

import logic
from storage import load_items, update_items

EMPTY_MESSAGE = "아직 아이템이 없어요. 위에서 추가해 보세요!"

# 라이트/다크 모드 모두에서 보이도록 색 대신 opacity로 흐리게 표시한다.
CUSTOM_CSS = """
<style>
.block-container { padding-top: 2.5rem; max-width: 640px; }
/* wrap=False 컬럼의 기본 min-width(128px)를 풀어 비율대로 배치하고, 행 내부 스크롤바를 없앤다. */
[data-testid="stHorizontalBlock"] { overflow: visible !important; }
[data-testid="stColumn"] { min-width: 0 !important; }
/* 좁은 화면에서 버튼 글자가 세로로 줄바꿈되지 않게 한다. */
.stButton button, [data-testid="stFormSubmitButton"] button { white-space: nowrap; padding-left: 0.5rem; padding-right: 0.5rem; }
.stButton button p, [data-testid="stFormSubmitButton"] button p { white-space: nowrap; }
/* 입력창 안의 영어 안내문("Press Enter to submit form")을 숨긴다. */
[data-testid="InputInstructions"] { display: none; }
/* 모바일 터치 영역을 44px 이상으로 확보한다. */
[data-testid="stCheckbox"] label { min-width: 44px; min-height: 44px; align-items: center; justify-content: center; }
[data-testid="stBaseButton-tertiary"] { min-width: 44px; min-height: 44px; }
.item-name { font-size: 1rem; line-height: 1.4; overflow-wrap: anywhere; }
.item-name.done { text-decoration: line-through; opacity: 0.45; }
.item-qty { font-size: 0.85rem; opacity: 0.6; margin-left: 0.35rem; white-space: nowrap; }
.empty-message { text-align: center; opacity: 0.6; padding: 2.5rem 0; }
</style>
"""

# 행 컬럼 비율: 체크박스 | 이름 | 수정 | 삭제
ROW_SPEC = [1, 5, 1, 1]
EDIT_ROW_SPEC = [3.4, 1.6, 1.3, 1.3]
ADD_ROW_SPEC = [4, 1.6, 1.4]


# ---------- 상태 관리 ----------
# 아이템 목록은 세션에 보관하지 않고 매번 파일에서 읽는다 (여러 탭·기기 동시 사용 대비).
# 세션 상태에는 화면 상태(수정 중인 아이템, 경고 메시지)만 둔다.

def init_state() -> None:
    """화면 상태를 초기화한다."""
    st.session_state.setdefault("editing_id", None)


def notify(message: str, icon: str) -> None:
    """사용자 입력이 섞인 알림을 Markdown 해석 없이 표시한다."""
    st.toast(logic.escape_markdown(message), icon=icon)


def apply_change(change: Callable[[list[dict]], list[dict]], error_key: str) -> bool:
    """최신 목록에 변경을 적용해 저장한다. 검증 실패 시 error_key에 메시지를 남기고 False."""
    try:
        update_items(change)
    except ValueError as err:
        st.session_state[error_key] = str(err)
        return False
    return True


def find_item(items: list[dict], item_id: str) -> dict | None:
    """id로 아이템을 찾는다."""
    return next((item for item in items if item["id"] == item_id), None)


# ---------- 콜백 ----------
# 콜백은 화면을 그리기 전에 실행되므로 진행률 등이 같은 실행에서 바로 반영된다.

def on_add() -> None:
    """추가 폼 제출: 검증 후 저장하고, 성공했을 때만 입력창을 비운다."""
    name = st.session_state["new_name"]
    quantity = st.session_state["new_qty"]
    if not apply_change(lambda items: logic.add_item(items, name, quantity), "add_error"):
        return
    st.session_state["new_name"] = ""
    st.session_state["new_qty"] = 1
    notify(f"'{logic.shorten(logic.normalize_name(name))}'을(를) 추가했어요.", "🛒")


def on_toggle(item_id: str) -> None:
    """체크박스 변경 시 체크 상태를 저장한다."""
    checked = st.session_state[f"check_{item_id}"]
    update_items(lambda items: logic.set_checked(items, item_id, checked))


def on_start_edit(item_id: str) -> None:
    """수정 모드로 전환하고 입력창에 최신 값을 채운다."""
    item = find_item(load_items(), item_id)
    if item is None:
        notify("다른 곳에서 이미 삭제된 아이템이에요.", "⚠️")
        return
    st.session_state["editing_id"] = item_id
    st.session_state.pop("edit_error", None)
    st.session_state[f"edit_name_{item_id}"] = item["name"]
    st.session_state[f"edit_qty_{item_id}"] = item["quantity"]


def on_cancel_edit() -> None:
    """수정 모드를 종료한다."""
    st.session_state["editing_id"] = None
    st.session_state.pop("edit_error", None)


def on_save_edit(item_id: str) -> None:
    """수정 내용을 검증 후 저장한다. 실패하면 수정 모드를 유지하고 경고를 남긴다."""
    name = st.session_state[f"edit_name_{item_id}"]
    quantity = st.session_state[f"edit_qty_{item_id}"]
    if apply_change(lambda items: logic.update_item(items, item_id, name, quantity), "edit_error"):
        on_cancel_edit()
        notify("수정했어요.", "✏️")


def on_delete(item_id: str) -> None:
    """아이템을 삭제한다."""
    deleted: list[dict] = []

    def change(items: list[dict]) -> list[dict]:
        if (item := find_item(items, item_id)) is not None:
            deleted.append(item)
        return logic.delete_item(items, item_id)

    update_items(change)
    if st.session_state["editing_id"] == item_id:
        on_cancel_edit()
    if deleted:
        notify(f"'{logic.shorten(deleted[0]['name'])}'을(를) 삭제했어요.", "🗑️")


def on_clear_checked() -> None:
    """체크된 아이템을 모두 삭제한다."""
    removed: list[dict] = []

    def change(items: list[dict]) -> list[dict]:
        removed.extend(item for item in items if item["checked"])
        return logic.clear_checked(items)

    update_items(change)
    if any(item["id"] == st.session_state["editing_id"] for item in removed):
        on_cancel_edit()
    notify(f"완료 항목 {len(removed)}개를 삭제했어요.", "🧹")


# ---------- 화면 ----------

def show_error_once(error_key: str) -> None:
    """남겨둔 경고를 한 번만 표시한다 (다음 실행에서는 사라짐)."""
    message = st.session_state.pop(error_key, None)
    if message:
        st.warning(logic.escape_markdown(message))


def render_header(items: list[dict]) -> None:
    """제목과 진행 현황 (F-08)."""
    st.title("🛒 쇼핑 리스트")
    done, total = logic.progress(items)
    if total:
        st.progress(done / total, text=f"{done} / {total} 구매 완료")


def render_add_form() -> None:
    """아이템 추가 폼 (F-01, F-09).

    길이 제한은 서버 검증(logic.validate_name)으로만 한다. max_chars를 쓰면 제한을 넘는
    붙여넣기가 안내 없이 통째로 무시된다.
    """
    with st.form("add_form", border=False):
        name_col, qty_col, btn_col = st.columns(
            ADD_ROW_SPEC, vertical_alignment="bottom", wrap=False
        )
        name_col.text_input(
            "아이템 이름",
            key="new_name",
            placeholder="아이템 이름 입력...",
            label_visibility="collapsed",
        )
        # value=를 주지 않는다: 기본값이 min_value(1)이고, on_add가 세션 상태로 값을 초기화하므로
        # value=를 함께 쓰면 Streamlit 정책 경고가 난다.
        qty_col.number_input(
            "수량",
            key="new_qty",
            min_value=logic.MIN_QUANTITY,
            step=1,
            label_visibility="collapsed",
        )
        btn_col.form_submit_button("추가", type="primary", width="stretch", on_click=on_add)
    show_error_once("add_error")


def item_label_html(item: dict) -> str:
    """아이템 이름과 수량을 표시할 HTML. st.html로 그려 Markdown 해석을 피하고, 이름은 이스케이프한다."""
    css_class = "item-name done" if item["checked"] else "item-name"
    qty = f'<span class="item-qty">× {item["quantity"]}</span>' if item["quantity"] > 1 else ""
    return f'<span class="{css_class}">{html.escape(item["name"])}</span>{qty}'


def render_edit_row(item: dict) -> None:
    """수정 모드 행 (F-03). 폼이라서 Enter를 누르면 첫 번째 버튼(저장)이 실행된다."""
    item_id = item["id"]
    with st.form(f"edit_form_{item_id}"):
        name_col, qty_col, save_col, cancel_col = st.columns(
            EDIT_ROW_SPEC, vertical_alignment="bottom", wrap=False
        )
        name_col.text_input(
            "이름 수정", key=f"edit_name_{item_id}", label_visibility="collapsed"
        )
        qty_col.number_input(
            "수량 수정",
            key=f"edit_qty_{item_id}",
            min_value=logic.MIN_QUANTITY,
            step=1,
            label_visibility="collapsed",
        )
        save_col.form_submit_button(
            "저장", type="primary", width="stretch", on_click=on_save_edit, args=(item_id,)
        )
        cancel_col.form_submit_button("취소", width="stretch", on_click=on_cancel_edit)
        show_error_once("edit_error")


def render_item_row(item: dict, editing: bool) -> None:
    """일반 행: 체크박스 | 이름 (수량) | 수정 | 삭제 (F-04, F-05).

    다른 아이템을 수정 중이면 수정·삭제 버튼을 잠가 입력 중인 내용이 사라지지 않게 한다.
    """
    item_id = item["id"]
    check_key = f"check_{item_id}"
    # 다른 탭에서 바뀐 체크 상태가 반영되도록 매번 파일 값으로 위젯 상태를 맞춘다.
    st.session_state[check_key] = item["checked"]
    check_col, name_col, edit_col, delete_col = st.columns(
        ROW_SPEC, vertical_alignment="center", gap="xxsmall", wrap=False
    )
    check_col.checkbox(
        item["name"],
        key=check_key,
        on_change=on_toggle,
        args=(item_id,),
        label_visibility="collapsed",
    )
    with name_col:
        st.html(item_label_html(item))
    edit_col.button(
        "✏️", key=f"edit_{item_id}", help="수정", type="tertiary", disabled=editing,
        on_click=on_start_edit, args=(item_id,),
    )
    delete_col.button(
        "🗑️", key=f"delete_{item_id}", help="삭제", type="tertiary", disabled=editing,
        on_click=on_delete, args=(item_id,),
    )


def render_items(items: list[dict]) -> None:
    """아이템 목록과 일괄 삭제 버튼 (F-02, F-07)."""
    if not items:
        st.markdown(
            f'<div class="empty-message">{EMPTY_MESSAGE}</div>', unsafe_allow_html=True
        )
        return

    editing_id = st.session_state["editing_id"]
    st.divider()
    for item in logic.sorted_for_display(items):
        if item["id"] == editing_id:
            render_edit_row(item)
        else:
            render_item_row(item, editing=editing_id is not None)

    done, _ = logic.progress(items)
    if done:
        st.divider()
        _, center, _ = st.columns([1, 2, 1], wrap=False)
        center.button("완료 항목 삭제", icon="🧹", width="stretch", on_click=on_clear_checked)


def main() -> None:
    """앱 진입점."""
    st.set_page_config(page_title="쇼핑 리스트", page_icon="🛒", layout="centered")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    init_state()
    items = load_items()
    # 수정 중이던 아이템이 다른 탭에서 삭제됐으면 수정 모드를 해제하고 알린다.
    editing_id = st.session_state["editing_id"]
    if editing_id is not None and find_item(items, editing_id) is None:
        on_cancel_edit()
        notify("다른 곳에서 삭제된 아이템이라 수정을 취소했어요.", "⚠️")
    render_header(items)
    render_add_form()
    render_items(items)


main()
