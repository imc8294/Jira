import streamlit as st
import base64
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, date
from dateutil.tz import tzlocal
from jira_client import JiraClient
import plotly.express as px
from ai_assistant import render_ai_assistant

# -------------------------------------------------
# Page config
# -------------------------------------------------
st.set_page_config(
    page_title="Innodata Jira Dashboard",
    layout="wide"
)

# -------------------------------------------------
# INITIALIZE JIRA CLIENT (Directly)
# -------------------------------------------------
# Replace these with your actual credentials or use st.secrets
JIRA_URL = "https://your-domain.atlassian.net"
JIRA_EMAIL = "your-email@example.com"
JIRA_TOKEN = "your-api-token"

if "client" not in st.session_state or st.session_state.client is None:
    try:
        st.session_state.client = JiraClient(JIRA_URL, JIRA_EMAIL, JIRA_TOKEN)
        me = st.session_state.client.get_myself()
        st.session_state.user_name = me["displayName"]
        st.session_state.logged_in = True
    except Exception as e:
        st.error(f"Failed to connect to Jira: {e}")
        st.stop()

# -------------------------------------------------
# Utils & Defaults
# -------------------------------------------------
def load_image_base64(path):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except:
        return ""

def format_started_iso(d, t):
    dt = datetime.combine(d, t)
    return dt.replace(tzinfo=tzlocal()).strftime("%Y-%m-%dT%H:%M:%S.000%z")

def extract_comment(comment):
    if not comment or not isinstance(comment, dict):
        return ""
    texts = []
    for block in comment.get("content", []):
        for item in block.get("content", []):
            if item.get("type") == "text":
                texts.append(item.get("text", ""))
    return " ".join(texts)

# Ensure session states exist
defaults = {
    "report_df": pd.DataFrame(),
    "issues": [],
    "all_worklogs": None,
    "page": "Dashboard",
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# -------------------------------------------------
# Sidebar Navigation
# -------------------------------------------------
with st.sidebar:
    logo_base64 = load_image_base64("assets/company-logo.png")
    if logo_base64:
        st.markdown(
            f"""<div style="display:flex;justify-content:center;margin-top:-30px;padding-bottom:12px;">
            <img src="data:image/png;base64,{logo_base64}" style="height:52px;" /></div>""",
            unsafe_allow_html=True
        )

    st.markdown(f"**👤 {st.session_state.user_name}**")
    st.markdown("---")

    def nav_button(label, page_name):
        is_active = st.session_state.page == page_name
        if st.button(label, use_container_width=True, type="primary" if is_active else "secondary"):
            st.session_state.page = page_name
            st.rerun()

    nav_button("📊 Dashboard", "Dashboard")
    nav_button("🐞 Issues", "Issues")
    nav_button("📝 Worklogs", "Worklogs")
    nav_button("📈 Reports", "Reports")
    nav_button("🤖 AI Assistant", "AI Assistant")

# Set reference variables
client = st.session_state.client
page = st.session_state.page

# -------------------------------------------------
# Data Loading Logic
# -------------------------------------------------
def load_all_worklogs():
    rows = []
    issues = client.get_my_issues(max_results=200)
    for issue in issues:
        issue_key = issue["key"]
        project = issue["fields"]["project"]["name"]
        for wl in client.get_worklogs(issue_key):
            rows.append({
                "Project": project,
                "Issue": issue_key,
                "Date": wl["started"][:10],
                "Hours": wl["timeSpentSeconds"] / 3600,
                "Author": wl["author"]["displayName"]
            })
    return pd.DataFrame(rows)

# -------------------------------------------------
# Page Routing
# -------------------------------------------------

if page == "Dashboard":
    st.markdown("<h1 style='text-align:center;'>📊 Jira Worklog Dashboard</h1>", unsafe_allow_html=True)
    
    if st.session_state.all_worklogs is None:
        with st.spinner("Loading worklogs..."):
            st.session_state.all_worklogs = load_all_worklogs()

    df = st.session_state.all_worklogs
    if df.empty:
        st.info("No worklogs found")
    else:
        df["Date"] = pd.to_datetime(df["Date"])
        df["Month"] = df["Date"].dt.to_period("M").astype(str)
        df["Year"] = df["Date"].dt.year

        chart_type = st.selectbox("Select Chart Type", ["Bar", "Line", "Area", "Pie"])

        def build_chart(data, x, y, title, color=None, hover_cols=None):
            if chart_type == "Bar": return px.bar(data, x=x, y=y, color=color, hover_data=hover_cols, title=title)
            elif chart_type == "Line": return px.line(data, x=x, y=y, color=color, hover_data=hover_cols, title=title)
            elif chart_type == "Area": return px.area(data, x=x, y=y, color=color, hover_data=hover_cols, title=title)
            elif chart_type == "Pie": return px.pie(data, names=x, values=y, hover_data=hover_cols, title=title)

        issue_df = df.groupby(["Issue", "Author"], as_index=False)["Hours"].sum()
        day_df = df.groupby(["Date", "Issue"], as_index=False)["Hours"].sum()
        
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(build_chart(issue_df, "Issue", "Hours", "Time by Issue", hover_cols=["Author"]), use_container_width=True)
        with col2:
            st.plotly_chart(build_chart(day_df, "Date", "Hours", "Time by Day", color="Issue"), use_container_width=True)

elif page == "Issues":
    st.title("🐞 Create Jira Issue")
    # ... (Rest of your issue creation logic)
    projects = client.get_projects()
    project_map = {f"{p['name']} ({p['key']})": p["key"] for p in projects}
    selected_project = st.selectbox("Select Project", list(project_map.keys()))
    issue_type = st.selectbox("Issue Type", ["Task", "Bug", "Story", "Epic"])
    summary = st.text_input("Summary")
    description = st.text_area("Description")
    
    if st.button("Create Issue"):
        if summary:
            with st.spinner("Creating..."):
                issue = client.create_issue(project_key=project_map[selected_project], summary=summary, description=description, issue_type=issue_type)
                st.success(f"✅ Issue created: {issue['key']}")

elif page == "Worklogs":
    st.title("📝 Add Worklogs")
    issues = client.get_my_issues()
    for issue in issues:
        with st.expander(f"{issue['key']} — {issue['fields']['summary']}"):
            with st.form(f"form_{issue['key']}", clear_on_submit=True):
                d = st.date_input("Date", date.today())
                t = st.time_input("Start Time")
                ts = st.text_input("Time Spent", "1h")
                c = st.text_area("Comment")
                if st.form_submit_button("Submit"):
                    client.add_worklog(issue['key'], ts, c, format_started_iso(d, t))
                    st.success("Worklog added")

elif page == "Reports":
    st.title("📋 Worklog Reports")
    # ... (Rest of your report logic)
    if st.button("Load Worklogs"):
        st.session_state.report_df = load_all_worklogs()
    
    if not st.session_state.report_df.empty:
        st.dataframe(st.session_state.report_df, use_container_width=True)

elif page == "AI Assistant":
    render_ai_assistant(client, load_all_worklogs)
