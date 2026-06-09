import streamlit as st
import pandas as pd
from datetime import date, timedelta
from api_client import check_health, run_day, get_episodes, get_system_metrics, get_pending_actions, approve_action, reject_action, trigger_execution_loop, get_kpi_window

st.set_page_config(page_title="ABOIA Console", layout="wide")

st.title("🚀 ABOIA – Governed AI Operations Console")

# =====================================================
# SESSION STATE
# =====================================================

if "sim_initialized" not in st.session_state:
    st.session_state.sim_initialized = False

if "current_date" not in st.session_state:
    st.session_state.current_date = None

if "sim_end_date" not in st.session_state:
    st.session_state.sim_end_date = None

if "start_date" not in st.session_state:
    st.session_state.start_date = None

if "end_date_picker" not in st.session_state:
    st.session_state.end_date_picker = None

# =====================================================
# SIDEBAR
# =====================================================

st.sidebar.subheader("Simulation Control")

api_key = st.sidebar.text_input("API Key", type="password")

if st.session_state.start_date is None:
    st.session_state.start_date = date(2017, 1, 22)

if st.session_state.end_date_picker is None:
    st.session_state.end_date_picker = date(2018, 9, 3) 

start_date = st.sidebar.date_input(
    "Start Date", 
    key="start_date"
)

end_date = st.sidebar.date_input(
    "End Date", 
    key="end_date_picker"
)

if st.sidebar.button("🚀 Initialize Simulation"):

    st.session_state.sim_initialized = True
    st.session_state.current_date = start_date
    st.session_state.sim_end_date = end_date
    st.session_state.last_scan_msg = None

    date_str = start_date.strftime("%Y-%m-%d")
    st.sidebar.info(f"Running simulation for {date_str}")
    eps_before = len(get_episodes())
    run_day(date_str, api_key)
    eps_after = len(get_episodes())
    
    if eps_after > eps_before:
        st.session_state.last_scan_msg = None
    else:
        st.session_state.last_scan_msg = f"✅ {date_str}: System Stable (No Anomalies)"

    st.session_state.current_date += timedelta(days=1)
    st.rerun()

if st.session_state.get("sim_initialized"):

    if st.session_state.current_date <= st.session_state.sim_end_date:

        if st.sidebar.button("▶ Run Next Day"):
            day = st.session_state.current_date
            date_str = day.strftime("%Y-%m-%d")
            
            st.sidebar.info(f"Running simulation for {date_str}")
            
            eps_before = len(get_episodes())
            run_day(date_str, api_key)
            eps_after = len(get_episodes())
            
            if eps_after > eps_before:
                st.session_state.last_scan_msg = None
            else:
                st.session_state.last_scan_msg = f"✅ {date_str}: System Stable (No Anomalies)"

            st.session_state.current_date += timedelta(days=1)
            st.rerun()

    else:
        st.sidebar.success("Simulation Completed")

if st.session_state.get("last_scan_msg"):
    st.sidebar.success(st.session_state.last_scan_msg)

st.sidebar.markdown("---")

if check_health():
    st.sidebar.success("Backend Connected")
else:
    st.sidebar.error("Backend Offline")

st.sidebar.subheader("Navigation")
view = st.sidebar.radio(
    "",
    ["📅 Timeline", "🔍 Episode Deep Dive", "📝 Pending Approvals", "⏱ SLA Monitor", "📊 System Metrics"],
    label_visibility="collapsed"
)

st.sidebar.markdown("---")
st.sidebar.subheader("Action Execution")
if st.sidebar.button("⚙️ Trigger Execution Loop"):
    sim_date = None
    if st.session_state.get("current_date"):
        # The current simulated state is the day before the 'next' day it's queued for
        sim_date = (st.session_state.current_date - timedelta(days=1)).strftime("%Y-%m-%d")
    success = trigger_execution_loop(api_key=api_key, simulated_date=sim_date)
    if success:
        st.sidebar.success("Execution worker triggered!")
    else:
        st.sidebar.error("Failed to trigger execution worker.")

episodes = get_episodes()

# =====================================================
# Helper Functions
# =====================================================

def risk_badge(level):

    if not level:
        return "⚪ UNKNOWN"

    level = level.upper()

    if level == "LOW":
        return "🟢 LOW"

    if level == "MEDIUM":
        return "🟠 MEDIUM"

    if level == "HIGH":
        return "🔴 HIGH"

    return level


def governance_badge(score):

    if score is None:
        return "⚪ N/A"


    if score >= 90:
        return f"🟢 {score}"

    if score >= 70:
        return f"🟠 {score}"

    return f"🔴 {score}"

def sla_badge(status):
    if not status:
        return "⚪ N/A"
        
    s = str(status).lower()
    if s == "active":
        return "🟢 ACTIVE"
    elif s == "breached":
        return "🔴 BREACHED"
    elif s == "resolved":
        return "🔵 RESOLVED"
        
    return s.upper()

# =====================================================
# TIMELINE
# =====================================================

# =====================================================
# PENDING APPROVALS
# =====================================================

if view == "📝 Pending Approvals":
    st.header("📝 Pending Approvals Inbox")
    pending_actions = get_pending_actions()

    if not pending_actions:
        st.info("No actions currently pending approval. You're all caught up!")
    else:
        for action in pending_actions:
            with st.container():
                st.markdown(f"### 🚨 {action.get('priority')} | {action.get('description')}")
                st.write(f"**Action ID:** `{action.get('action_id')}`")
                st.write(f"**Owner:** {action.get('owner')}")
                st.write(f"**SLA Deadline:** {action.get('sla_deadline')}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Approve", key=f"approve_{action.get('action_id')}"):
                        success = approve_action(action.get('action_id'), api_key)
                        if success:
                            st.success(f"Action {action.get('action_id')} Approved!")
                            st.rerun()
                        else:
                            st.error("Failed to approve action.")
                with col2:
                    if st.button("❌ Reject", key=f"reject_{action.get('action_id')}"):
                        success = reject_action(action.get('action_id'), api_key)
                        if success:
                            st.success(f"Action {action.get('action_id')} Rejected!")
                            st.rerun()
                        else:
                            st.error("Failed to reject action.")
            st.markdown("---")

# =====================================================
# TIMELINE
# =====================================================

elif view == "📅 Timeline":

    st.header("📅 Episode Timeline")

    if not episodes:
        st.info("No episodes yet. Initialize simulation to start.")

    else:

        rows = []

        for ep in episodes:

            reasoning = ep.get("reasoning", {})
            evaluation = ep.get("evaluation", {})
            validation = ep.get("validation", {})

            risk = risk_badge(ep.get("risk_level"))

            score = governance_badge(
                evaluation.get("overall_reasoning_score")
            )

            actions = len(ep.get("actions", []))

            severity_raw = validation.get("severity", "none").lower()
            if severity_raw == "none":
                severity_display = "✅ PASSED"
            elif severity_raw == "warning":
                severity_display = "⚠️ WARNING"
            elif severity_raw == "critical":
                severity_display = "❌ FAILED"
            else:
                severity_display = "⚪ UNKNOWN"

            priority = ep.get("priority", "Normal").capitalize()

            rows.append({
                "Date": str(ep.get("created_at")).split("T")[0],
                "Risk": risk,
                "Priority": priority,
                "Governance Score": score,
                "AI Validation": severity_display,
                "Actions": actions
            })

        df = pd.DataFrame(rows)

        st.dataframe(df, use_container_width=True)

# =====================================================
# EPISODE DEEP DIVE
# =====================================================

elif view == "🔍 Episode Deep Dive":

    st.header("🔍 Episode Deep Dive")

    if not episodes:
        st.info("No episodes yet.")

    else:

        ep_id = st.selectbox(
            "Select Episode",
            [ep["episode_id"] for ep in episodes]
        )

        ep = next(e for e in episodes if e["episode_id"] == ep_id)

        reasoning = ep.get("reasoning", {})
        evaluation = ep.get("evaluation", {})
        actions = ep.get("actions", [])

        # Determine Episode Overall Status
        has_pending = any(a.get("status") == "pending_approval" for a in actions)
        all_resolved = all(a.get("status") in ["completed", "failed", "rejected"] for a in actions) if actions else True
        has_execution_pending = any(a.get("status") in ["approved", "in_progress"] for a in actions)

        # Build Visual Timeline
        st.markdown("### 🚦 Episode Lifecycle")
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.success("🚨 Detected")
        with col2:
            st.success("🧠 Analyzed")
        with col3:
            st.success("📋 Planned")
        with col4:
            if has_pending:
                st.warning("⏳ Awaiting Approval")
            else:
                st.success("✅ Approvals Done")
        with col5:
            if all_resolved:
                st.success("✅ Execution Resolved")
            elif has_execution_pending:
                st.info("⏳ Execution Pending/Active")
            else:
                st.error("🔒 Blocked by Approval")
                
        st.markdown("---")

        with st.expander("🧠 AI Reasoning", expanded=True):

            st.write("**Root Cause:**", reasoning.get("root_cause"))
            st.write("**Business Impact:**",reasoning.get("business_impact"))

            st.write("**Risk:**", reasoning.get("risk_level"))
            st.write("**Anomaly Confidence:**", reasoning.get("anomaly_confidence"))
            st.write("**Reasoning Confidence:**", reasoning.get("reasoning_confidence"))

        with st.expander("🛡 Governance Evaluation", expanded=True):

            overall = evaluation.get("overall_reasoning_score")
            
            if overall:
                st.markdown(f"#### Overall Governance Score: {governance_badge(overall)}")



                explanations = evaluation.get("explanations", {})
                if explanations:
                    st.markdown("#### Evaluation Reasoning")
                    
                    if "grounding" in explanations:
                        score_val = evaluation.get("grounding_score", "N/A")
                        with st.expander(f"🔍 Grounding Score: {score_val}"):
                            st.write(explanations["grounding"])
                            
                    if "risk_alignment" in explanations:
                        score_val = evaluation.get("risk_alignment_score", "N/A")
                        with st.expander(f"⚖️ Risk Alignment Score: {score_val}"):
                            st.write(explanations["risk_alignment"])
                            
                    if "confidence_gap" in explanations:
                        score_val = evaluation.get("confidence_gap_score", "N/A")
                        with st.expander(f"📊 Confidence Gap Score: {score_val}"):
                            st.write(explanations["confidence_gap"])
                            
                    if "analytical_depth" in explanations:
                        score_val = evaluation.get("analytical_depth_score", "N/A")
                        with st.expander(f"🧠 Analytical Depth Score: {score_val}"):
                            st.write(explanations["analytical_depth"])

        metrics_affected = reasoning.get("metrics_affected", [])
        if metrics_affected:
            with st.expander("📉 Episode Metric Plots", expanded=False):
                ep_date = ep.get("created_at", "").split(" ")[0]
                if ep_date:
                    kpi_data = get_kpi_window(end_date=ep_date, metrics=metrics_affected, window_days=7)
                    if kpi_data and "dates" in kpi_data:
                        plot_df = pd.DataFrame(kpi_data)
                        plot_df.set_index("dates", inplace=True)
                        
                        cols = st.columns(2)
                        for i, m in enumerate(metrics_affected):
                            if m in plot_df.columns:
                                with cols[i % 2]:
                                    st.markdown(f"**{m.replace('_', ' ').title()} (7-Day Context)**")
                                    st.line_chart(plot_df[m])
                    else:
                        st.info("No historical KPI data available for this episode.")

        with st.expander("📋 Action Plan", expanded=True):

            if not actions:
                st.info("No actions")

            else:

                for a in actions:

                    st.markdown(f"#### {a.get('type')} | 🚨 {a.get('priority')}")
                    
                    st.write("**Description:**", a.get("description"))

                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("**Owner:**", a.get("owner"))
                    with col2:
                        st.write("**Status:**", str(a.get("status")).replace("_", " ").title())

                    # Show approval block if an approval role exists or if it has a status
                    approval_role = a.get("approval_role")
                    approval_status = a.get("approval_status")
                    
                    if approval_role or approval_status:
                        st.info(f"👔 **Approval Required:** {approval_role} ({str(approval_status).upper()})")

                    error_message = a.get("error_message")
                    if error_message:
                        st.error(f"❌ **Execution Error:** {error_message}")

                    st.markdown("---")

# =====================================================
# SLA MONITOR
# =====================================================

elif view == "⏱ SLA Monitor":

    st.header("⏱ SLA Monitoring")

    rows = []

    for ep in episodes:

        for a in ep.get("actions", []):
            
            # Inbox Zero: Hide resolved/finished actions from the active SLA queue!
            if a.get("status") in ["completed", "failed", "rejected"] or a.get("sla_status") == "resolved":
                continue

            rows.append({
                "Episode": ep["episode_id"],
                "Action": a.get("action_id"),
                "Owner": a.get("owner"),
                "Priority": a.get("priority"),
                "SLA Status": sla_badge(a.get("sla_status")),
                "Status": str(a.get("status")).replace("_", " ").title(),
            })

    if rows:

        df = pd.DataFrame(rows)

        st.dataframe(df, use_container_width=True)

    else:
        st.info("No SLA records")

# =====================================================
# SYSTEM METRICS
# =====================================================

elif view == "📊 System Metrics":

    st.header("📊 System Metrics")

    metrics = get_system_metrics()

    if metrics:

        col1,col2,col3 = st.columns(3)
        col4,col5,col6 = st.columns(3)

        col1.metric("Total Episodes", metrics["total_episodes"])
        col2.metric("Total Actions", metrics["total_actions"])
        col3.metric("Pending Approvals", metrics["pending_approvals"])

        col4.metric("SLA Breaches", metrics["sla_breaches"])
        col5.metric("Completed Actions", metrics["completed_actions"])
        col6.metric("Failed Actions", metrics["failed_actions"])