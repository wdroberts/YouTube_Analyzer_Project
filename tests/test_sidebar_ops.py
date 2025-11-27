import streamlit as st

from sidebar_ops import record_sidebar_operation


def setup_function():
    """Reset Streamlit session state between tests."""
    st.session_state.clear()


def test_record_sidebar_operation_creates_entry():
    record_sidebar_operation("TestOp", "success", message="ok", project_dir="proj1")
    assert "recent_operations" in st.session_state
    recent = st.session_state["recent_operations"]
    assert len(recent) == 1
    entry = recent[0]
    assert entry["operation"] == "TestOp"
    assert entry["status"] == "success"
    assert entry["message"] == "ok"
    assert entry["project_dir"] == "proj1"


def test_record_sidebar_operation_limits_entries():
    for i in range(10):
        record_sidebar_operation(f"op{i}", "info")

    recent = st.session_state["recent_operations"]
    assert len(recent) == 8
    assert recent[0]["operation"] == "op9"
    assert recent[-1]["operation"] == "op2"

