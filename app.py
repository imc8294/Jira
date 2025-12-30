import streamlit as st
import base64
import pandas as pd
import plotly.express as px
from datetime import datetime, date
from dateutil.tz import tzlocal
from jira_client import JiraClient
from ai_assistant import render_ai_assistant

# -------------------------------------------------
# 1. GLOBAL CONFIG
# -------------------------------------------------
st.set_page_config(
    page_title="Innodata Jira Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------------------------------
# 2. SESSION STATE INITIALIZATION
# -------------------------------------------------
def init_session():
    defaults = {
        "logged_in": False,
        "client": None,
        "user_name": "",
        "page": "Dashboard",
        "all_worklogs": None,
        "report_df": pd.DataFrame(),
        "projects": None,
        "issues": []
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

init_session()

# -------------------------------------------------
# 3. UTILS
# -------------------------------------------------
def load_image_base64(path):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except:
        return None

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

def load_all_worklogs(client):
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
# 4. LOGIN INTERFACE (Shared for all users)
# -------------------------------------------------
def show_login_page():
    st.markdown("""
        <div style="text-align: center; padding: 40px 0px;">
            <h1 style="font-size: 2.5rem; color: #1A6173;">🚀 Jira Worklog Manager</h1>
            <p style="font-size: 1.1rem; color: #555;">Track, manage, and analyze your productivity.</p>
        </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        with st.form("login_form"):
            st.subheader("🔐 User Login")
            base_url = st.text_input("Jira Base URL", placeholder="https://company.atlassian.net")
            email = st.text_input("Email Address")
            token = st.text_input("API Token", type="password", help="Use an Atlassian API Token, not your password.")
            submit = st.form_submit_button("Sign In", use_container_width=True)

            if submit:
                if not (base_url and email and token):
                    st.error("Please fill in all fields.")
                else:
                    try:
                        with st.spinner("Authenticating..."):
                            client = JiraClient(base_url.strip(), email.strip(), token.strip())
                            me = client.get_myself()
                            st.session_state.client = client
                            st.session_state.user_name = me["displayName"]
                            st.session_state.logged_in = True
                            st.rerun()
                    except Exception as e:
                        st.error(f"Login failed: Incorrect credentials or Jira URL.")

        st.info("💡 **Pro Tip:** Generate your token [here](https://id.atlassian.com/manage-profile/security/api-tokens).")

# -------------------------------------------------
# 5. MAIN APPLICATION (The "Inside")
# -------------------------------------------------
if not st.session_state.logged_in:
    show_login_page()
else:
    client = st.session_state.client

    # --- SIDEBAR NAVIGATION ---
    with st.sidebar:
        logo_base64 = load_image_base64("assets/company-logo.png")
        if logo_base64:
            st.markdown(f'<div style="text-align:center;"><img src="data:image/png;base64,{logo_base64}" style="height:52px;" /></div>', unsafe_allow_html=True)
        
        st.markdown(f"<h3 style='text-align:center;'>👤 {st.session_state.user_name}</h3>", unsafe_allow_html=True)
        st.divider()

        def nav_item(label, target):
            if st.button(label, use_container_width=True, type="primary" if st.session_state.page == target else "secondary"):
                st.session_state.page = target
                st.rerun()

        nav_item("📊 Dashboard", "Dashboard")
        nav_item("🐞 Issues", "Issues")
        nav_item("📝 Worklogs", "Worklogs")
        nav_item("📈 Reports", "Reports")
        nav_item("🤖 AI Assistant", "AI Assistant")

        st.spacer = st.empty()
        if st.button("🚪 Logout", use_container_width=True):
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.rerun()

    # --- PAGE ROUTING ---
    page = st.session_state.page

    if page == "Dashboard":
        st.markdown("<h1 style='text-align:center;'>📊 My Worklog Dashboard</h1>", unsafe_allow_html=True)
        
        if st.session_state.all_worklogs is None:
            with st.spinner("Fetching data..."):
                st.session_state.all_worklogs = load_all_worklogs(client)
        
        df = st.session_state.all_worklogs
        if df.empty:
            st.info("No worklogs found for your account.")
        else:
            df["Date"] = pd.to_datetime(df["Date"])
            chart_type = st.selectbox("Chart Style", ["Bar", "Line", "Pie"])
            
            # Simplified Chart Logic
            fig = px.bar(df, x="Date", y="Hours", color="Issue", title="Hours Logged per Day")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df, use_container_width=True)

    elif page == "Issues":
        st.title("🐞 Create Jira Issue")
        if st.session_state.projects is None:
            st.session_state.projects = client.get_projects()
        
        project_map = {f"{p['name']} ({p['key']})": p["key"] for p in st.session_state.projects}
        sel_project = st.selectbox("Select Project", list(project_map.keys()))
        issue_type = st.selectbox("Issue Type", ["Task", "Bug", "Story", "Epic"])
        summary = st.text_input("Summary")
        desc = st.text_area("Description")

        if st.button("Create"):
            if summary:
                res = client.create_issue(project_map[sel_project], summary, desc, issue_type)
                st.success(f"Created {res['key']}")

    elif page == "Worklogs":
        st.title("📝 Add Worklogs")
        st.session_state.issues = client.get_my_issues()
        for issue in st.session_state.issues:
            with st.expander(f"{issue['key']} — {issue['fields']['summary']}"):
                with st.form(f"form_{issue['key']}"):
                    d = st.date_input("Date", date.today())
                    ts = st.text_input("Time Spent", "1h")
                    c = st.text_area("Comment")
                    if st.form_submit_button("Submit Worklog"):
                        client.add_worklog(issue['key'], ts, c, format_started_iso(d, datetime.now().time()))
                        st.success("Worklog Saved!")

    elif page == "Reports":
        st.title("📋 Reports")
        if st.button("Generate Report"):
            st.session_state.report_df = load_all_worklogs(client)
        
        if not st.session_state.report_df.empty:
            st.dataframe(st.session_state.report_df, use_container_width=True)

    elif page == "AI Assistant":
        render_ai_assistant(client, lambda: load_all_worklogs(client))
