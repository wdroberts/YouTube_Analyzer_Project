from datetime import datetime
from typing import Optional

import streamlit as st


def record_sidebar_operation(
    operation: str,
    status: str,
    message: str = "",
    project_dir: Optional[str] = None
) -> None:
    """
    Record an operation in the sidebar's recent operations feed.
    """
    if "recent_operations" not in st.session_state:
        st.session_state["recent_operations"] = []

    entry = {
        "timestamp": datetime.now().isoformat(),
        "operation": operation,
        "status": status,
        "message": message,
        "project_dir": project_dir
    }

    recent_ops = st.session_state["recent_operations"]
    recent_ops.insert(0, entry)
    st.session_state["recent_operations"] = recent_ops[:8]

