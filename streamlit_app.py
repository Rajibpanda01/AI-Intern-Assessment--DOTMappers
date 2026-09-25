import csv
from html import escape
from io import StringIO

import streamlit as st

from app.config import get_settings
from app.data.loader import load_tickets
from app.services.anomaly_service import AnomalyService
from app.services.query_service import QueryService


st.set_page_config(
    page_title="Support Ticket AI",
    page_icon="S",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
        --ink: #17212b;
        --muted: #667482;
        --line: #d8e0e6;
        --panel: #ffffff;
        --canvas: #f4f7f9;
        --teal: #087f8c;
        --teal-soft: #e4f3f4;
        --amber-soft: #fff4db;
    }

    .stApp { background: var(--canvas); color: var(--ink); }
    [data-testid="stAppViewContainer"] > .main { background: var(--canvas); }
    .block-container { max-width: 1440px; padding-top: 2rem; padding-bottom: 3rem; }
    [data-testid="stSidebar"] { background: #eef3f5; border-right: 1px solid var(--line); }
    [data-testid="stSidebar"] .block-container { padding-top: 2rem; }
    [data-testid="stMetric"] {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 10px;
        padding: 1rem 1.1rem;
        box-shadow: 0 2px 8px rgba(23, 33, 43, 0.04);
    }
    [data-testid="stMetricLabel"] { color: var(--muted); font-size: 0.78rem; }
    [data-testid="stMetricValue"] { color: var(--ink); font-size: 1.6rem; }
    .eyebrow { color: var(--teal); font-size: 0.73rem; font-weight: 700; letter-spacing: 0.12em; }
    .page-subtitle { color: var(--muted); margin-top: -0.55rem; margin-bottom: 1.35rem; }
    .section-label { color: var(--muted); font-size: 0.72rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; }
    .result-panel {
        background: var(--panel);
        border: 1px solid var(--line);
        border-left: 4px solid var(--teal);
        border-radius: 8px;
        padding: 1rem 1.15rem;
        margin: 0.8rem 0 1rem;
    }
    .result-answer { color: var(--ink); font-size: 1.08rem; line-height: 1.5; }
    .status-note { color: var(--muted); font-size: 0.82rem; line-height: 1.45; }
    div[data-testid="stButton"] > button[kind="primary"] {
        background: var(--teal);
        border-color: var(--teal);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


settings = get_settings()
rows = load_tickets()


EXAMPLES = [
    "How many tickets are currently open?",
    "Which agent resolved the most tickets this month?",
    "Show me all Critical tickets not resolved within 12 hours.",
    "What is the average customer rating for Technical category tickets?",
    "Are there any anomalies in resolution times this week?",
]


def display_ticket(row: dict) -> dict:
    result = dict(row)
    created_at = result.get("created_at")
    if hasattr(created_at, "isoformat"):
        result["created_at"] = created_at.isoformat(timespec="minutes")
    return result


def csv_download(records: list[dict]) -> str:
    if not records:
        return ""
    output = StringIO()
    fieldnames = list(records[0])
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(records)
    return output.getvalue()


def set_example() -> None:
    st.session_state.question = st.session_state.example_question


if "question" not in st.session_state:
    st.session_state.question = EXAMPLES[0]
if "query_result" not in st.session_state:
    st.session_state.query_result = None
if "anomaly_result" not in st.session_state:
    st.session_state.anomaly_result = None


with st.sidebar:
    st.markdown('<div class="section-label">Workspace</div>', unsafe_allow_html=True)
    st.markdown("## Ticket operations")
    st.caption("Explore the support dataset, ask questions, and review unusual activity.")

    st.divider()
    st.markdown('<div class="section-label">Ask a question</div>', unsafe_allow_html=True)
    st.selectbox(
        "Example questions",
        EXAMPLES,
        key="example_question",
        on_change=set_example,
        label_visibility="collapsed",
    )

    st.divider()
    st.markdown('<div class="section-label">System status</div>', unsafe_allow_html=True)
    provider = settings.llm_provider.replace("-", " ").title()
    st.markdown(f"**LLM provider**  \n{provider}")
    st.markdown(f"**Dataset**  \n{len(rows):,} tickets")
    st.markdown(
        '<p class="status-note">Answers are calculated from the CSV first. The model is used for question understanding and answer phrasing.</p>',
        unsafe_allow_html=True,
    )


st.markdown('<div class="eyebrow">SUPPORT OPERATIONS CONSOLE</div>', unsafe_allow_html=True)
st.title("Support Ticket AI")
st.markdown(
    '<div class="page-subtitle">A focused view of ticket volume, agent performance, customer ratings, and operational risk.</div>',
    unsafe_allow_html=True,
)

metric_cols = st.columns(4)
metric_cols[0].metric("Total tickets", f"{len(rows):,}")
metric_cols[1].metric("Open", sum(row["status"] == "Open" for row in rows))
metric_cols[2].metric("Escalated", sum(row["status"] == "Escalated" for row in rows))
metric_cols[3].metric("Resolved", sum(row["status"] == "Resolved" for row in rows))

st.write("")
query_tab, anomaly_tab, explorer_tab = st.tabs(["Ask the data", "Anomaly monitor", "Ticket explorer"])

with query_tab:
    st.markdown('<div class="section-label">Natural language query</div>', unsafe_allow_html=True)
    st.subheader("Ask a question about the tickets")
    with st.form("query_form"):
        st.text_area(
            "Question",
            key="question",
            height=96,
            label_visibility="collapsed",
            placeholder="For example: Which agent resolved the most tickets this month?",
        )
        submitted = st.form_submit_button("Run query", type="primary", use_container_width=True)

    if submitted:
        with st.spinner("Analysing tickets..."):
            st.session_state.query_result = QueryService(settings).run(st.session_state.question, rows)

    result = st.session_state.query_result
    if result:
        st.markdown(
            f'<div class="result-panel"><div class="result-answer">{escape(result["answer"])}</div></div>',
            unsafe_allow_html=True,
        )
        meta_cols = st.columns([1, 1, 4])
        meta_cols[0].caption(f"Intent: {result['intent']}")
        meta_cols[1].caption(f"Model: {result['model']}")

        if result["data"]:
            st.markdown("**Result details**")
            st.dataframe(result["data"], use_container_width=True, hide_index=True)
        if result["evidence"]:
            with st.expander(f"Evidence tickets ({len(result['evidence'])})"):
                st.dataframe(result["evidence"], use_container_width=True, hide_index=True)
                st.download_button(
                    "Download evidence",
                    csv_download(result["evidence"]),
                    "query_evidence.csv",
                    "text/csv",
                    key="download_query_evidence",
                )
    else:
        st.info("Choose an example or write a question, then run the query.")

with anomaly_tab:
    st.markdown('<div class="section-label">Risk review</div>', unsafe_allow_html=True)
    st.subheader("Find tickets that need attention")
    st.caption("The monitor checks long resolutions, slow first responses, and old unresolved High or Critical tickets.")

    with st.form("anomaly_form"):
        anomaly_cols = st.columns([1, 1, 3])
        threshold = anomaly_cols[0].number_input(
            "Unresolved age (hours)", min_value=1.0, value=24.0, step=1.0
        )
        limit = anomaly_cols[1].number_input("Rows to show", min_value=1, max_value=200, value=50, step=1)
        scan = anomaly_cols[2].form_submit_button("Scan for anomalies", type="primary")

    if scan:
        with st.spinner("Scanning ticket history..."):
            st.session_state.anomaly_result = AnomalyService().detect(rows, threshold, limit)

    anomaly_result = st.session_state.anomaly_result
    if anomaly_result:
        summary = anomaly_result["summary"]
        summary_cols = st.columns(4)
        summary_cols[0].metric("Total flagged", summary["total"])
        summary_cols[1].metric("Critical", summary["critical"])
        summary_cols[2].metric("High", summary["high"])
        summary_cols[3].metric("Medium", summary["medium"])

        anomaly_records = [
            {
                "ticket_id": item["ticket"]["ticket_id"],
                "type": item["anomaly_type"].replace("_", " ").title(),
                "severity": item["severity"].title(),
                "status": item["ticket"]["status"],
                "priority": item["ticket"]["priority"],
                "reason": item["reason"],
            }
            for item in anomaly_result["anomalies"]
        ]
        if anomaly_records:
            st.dataframe(anomaly_records, use_container_width=True, hide_index=True)
            st.download_button(
                "Download anomaly report",
                csv_download(anomaly_records),
                "anomaly_report.csv",
                "text/csv",
                key="download_anomalies",
            )
        else:
            st.success("No anomalies found for the selected threshold.")
    else:
        st.info("Set a threshold and run a scan to review flagged tickets.")

with explorer_tab:
    st.markdown('<div class="section-label">Dataset browser</div>', unsafe_allow_html=True)
    st.subheader("Browse tickets")
    filter_cols = st.columns(5)
    status_filter = filter_cols[0].selectbox("Status", ["All", "Open", "Resolved", "Escalated"])
    category_filter = filter_cols[1].selectbox("Category", ["All", "Billing", "Technical", "General"])
    priority_filter = filter_cols[2].selectbox("Priority", ["All", "Low", "Medium", "High", "Critical"])
    agents = sorted({row["agent_id"] for row in rows})
    agent_filter = filter_cols[3].selectbox("Agent", ["All", *agents])
    search = filter_cols[4].text_input("Search", placeholder="Issue text")

    filtered_rows = []
    for row in rows:
        if status_filter != "All" and row["status"] != status_filter:
            continue
        if category_filter != "All" and row["category"] != category_filter:
            continue
        if priority_filter != "All" and row["priority"] != priority_filter:
            continue
        if agent_filter != "All" and row["agent_id"] != agent_filter:
            continue
        if search and search.lower() not in row["issue_summary"].lower():
            continue
        filtered_rows.append(display_ticket(row))

    table_cols = st.columns([3, 1])
    table_cols[0].caption(f"Showing {len(filtered_rows):,} of {len(rows):,} tickets")
    table_cols[1].download_button(
        "Download CSV",
        csv_download(filtered_rows),
        "filtered_tickets.csv",
        "text/csv",
        key="download_tickets",
        use_container_width=True,
    )
    st.dataframe(filtered_rows, use_container_width=True, hide_index=True, height=520)
