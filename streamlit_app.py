import streamlit as st

from app.config import get_settings
from app.data.loader import load_tickets
from app.services.anomaly_service import AnomalyService
from app.services.query_service import QueryService


st.set_page_config(page_title="Support Ticket AI", page_icon="S", layout="wide")
settings = get_settings()
rows = load_tickets()

st.title("Support Ticket AI")
st.caption(f"{len(rows):,} tickets | grounded analytics | LLM provider: {settings.llm_provider}")

metric_cols = st.columns(4)
metric_cols[0].metric("Tickets", len(rows))
metric_cols[1].metric("Open", sum(row["status"] == "Open" for row in rows))
metric_cols[2].metric("Escalated", sum(row["status"] == "Escalated" for row in rows))
metric_cols[3].metric("Resolved", sum(row["status"] == "Resolved" for row in rows))

st.divider()
left, right = st.columns([1.35, 1])
with left:
    st.subheader("Ask the ticket data")
    question = st.text_area(
        "Question",
        value="How many critical tickets are unresolved?",
        height=90,
        label_visibility="collapsed",
    )
    if st.button("Run query", type="primary", use_container_width=True):
        result = QueryService(settings).run(question, rows)
        st.success(result["answer"])
        st.caption(f"Intent: {result['intent']} | Answer model: {result['model']}")
        if result["data"]:
            st.dataframe(result["data"], use_container_width=True, hide_index=True)
        if result["evidence"]:
            with st.expander("Evidence tickets"):
                st.dataframe(result["evidence"], use_container_width=True, hide_index=True)

with right:
    st.subheader("Anomaly monitor")
    threshold = st.number_input("Stale unresolved threshold (hours)", min_value=1.0, value=24.0, step=1.0)
    if st.button("Scan for anomalies", use_container_width=True):
        result = AnomalyService().detect(rows, threshold)
        st.write(result["summary"])
        if result["anomalies"]:
            st.dataframe(
                [
                    {
                        "type": item["anomaly_type"],
                        "severity": item["severity"],
                        "ticket": item["ticket"]["ticket_id"],
                        "reason": item["reason"],
                    }
                    for item in result["anomalies"]
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No anomalies found for the current thresholds.")

st.divider()
st.subheader("Ticket explorer")
st.dataframe(
    [
        {
            **row,
            "created_at": row["created_at"].isoformat(timespec="minutes"),
        }
        for row in rows
    ],
    use_container_width=True,
    hide_index=True,
)
