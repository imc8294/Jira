import streamlit as st
import streamlit.components.v1 as components
import base64
import pandas as pd
import plotly.express as px
from datetime import datetime, date
from dateutil.tz import tzlocal

# Custom imports - Ensure these files exist in your directory
from jira_client import JiraClient
from ai_assistant import render_ai_assistant

# -------------------------------------------------
# 1. JIRA CONTEXT BRIDGE (Get Project Key)
# -------------------------------------------------
def get_jira_context():
    components.html(
        """
        <script src="https://connect-cdn.atl-paas.net/all.js"></script>
        <script>
            if (window.AP) {
                window.AP.getContext(function(context){
                    const projectKey = context.jira.project.key;
                    const url = new URL(window.location.href);
                    
                    // ONLY redirect if the project_key in the URL is different from Jira context
                    if (url.searchParams.get("project_key") !== projectKey) {
                        url.searchParams.set("project_key", projectKey);
                        // Use replace to avoid messiness in browser history
                        window.location.replace(url.href); 
                    }
                });
            }
        </script>
        """,
        height=0,
    )

# Run the bridge to get the Project Key
get_jira_context()
project_key = st.experimental_get_query_params().get("project_key", ["Global"])[0]

# -------------------------------------------------
# 2. Page Configuration
# -------------------------------------------------
st.set_page_config(
    page_title=f"Innodata Jira Dashboard - {project_key}",
    page_icon="🚀",
    layout="wide"
)

# -------------------------------------------------
# 3. Utility Functions
# -------------------------------------------------
def encode(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode()

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
    # If we have a project key, we could filter here (e.g., client.get_issues(project=project_key))
    issues = client.get_my_issues(max_results=100)
    for issue in issues:
        issue_key = issue["key"]
        project = issue["fields"]["project"]["name"]
        worklogs = client.get_worklogs(issue_key)
        for wl in worklogs:
            rows.append({
                "Project": project,
                "Issue": issue_key,
                "Date": wl["started"][:10],
                "Hours": round(wl["timeSpentSeconds"] / 3600, 2),
                "Author": wl["author"]["displayName"],
                "Comment": extract_comment(wl.get("comment"))
            })
    return pd.DataFrame(rows)

# -------------------------------------------------
# 4. Session State Initialization
# -------------------------------------------------
defaults = {
    "client": None,
    "logged_in": False,
    "user_name": "",
    "page": "Dashboard",
    "all_worklogs": None,
    "report_df": pd.DataFrame(),
    "projects": None,
    "issues": []
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# -------------------------------------------------
# 5. Authentication Logic (Forge Auto-Login)
# -------------------------------------------------
import jwt

# Get the JWT token from the query parameters
token = st.experimental_get_query_params().get("token", [None])[0]

# Auto-login via Forge JWT
if not st.session_state.logged_in and token:
    try:
        # Decode the JWT using your secret from secrets.toml
        decoded = jwt.decode(token, st.secrets["JWT_SECRET"], algorithms=["HS256"])
        account_id = decoded["sub"]  # Forge user ID

        # Create Jira client (pass the JWT token or account_id as needed)
        base_url = st.secrets["JIRA_BASE_URL"]
        client = JiraClient(base_url, jwt_token=token)

        # Fetch user info
        me = client.get_myself()

        st.session_state.update({
            "client": client,
            "logged_in": True,
            "user_name": me["displayName"]
        })

        st.experimental_rerun()
    except Exception as e:
        st.error(f"Forge Auto-login failed: {e}")


# -------------------------------------------------
# 6. Conditional UI: Login vs Main App
# -------------------------------------------------
if not st.session_state.logged_in:
    # --- LANDING PAGE ---
    st.markdown("""
        <div style="text-align: center; padding: 20px;">
            <h1 style="font-size: 3.5rem; color: #1A6173;">🚀 Jira Worklog Manager</h1>
            <p style="font-size: 1.2rem; color: #555;">Track, manage, and analyze your productivity seamlessly.</p>
            <p style="color: #888;">Project Context: <b>{0}</b></p>
        </div>
        <hr>
    """.format(project_key), unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    col1.metric("Visibility", "Interactive Dashboards")
    col2.metric("Efficiency", "Fast Worklogging")
    col3.metric("Insights", "AI Assistant")

    with st.sidebar:
        st.header("🔐 User Login")
        url = st.text_input("Jira Base URL", placeholder="https://company.atlassian.net")
        email = st.text_input("Email")
        token = st.text_input("API Token", type="password")
        
        if st.button("Login", use_container_width=True, type="primary"):
            try:
                client = JiraClient(url.strip(), email.strip(), token.strip())
                me = client.get_myself()
                st.session_state.update({
                    "client": client,
                    "logged_in": True,
                    "user_name": me["displayName"]
                })
                st.rerun()
            except Exception as e:
                st.error(f"Login failed: {e}")
    st.stop()

# -------------------------------------------------
# 7. Main App Sidebar (Post-Login)
# -------------------------------------------------
client = st.session_state.client

with st.sidebar:
    st.markdown(f"### 👤 {st.session_state.user_name}")
    st.info(f"📍 Project: {project_key}")
    st.divider()
    
    pages = {
        "📊 Dashboard": "Dashboard",
        "🐞 Issues": "Issues",
        "📝 Worklogs": "Worklogs",
        "📈 Reports": "Reports",
        "🤖 AI Assistant": "AI Assistant"
    }

    for label, target in pages.items():
        if st.button(label, use_container_width=True, type="primary" if st.session_state.page == target else "secondary"):
            st.session_state.page = target
            st.rerun()

    st.divider()
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# -------------------------------------------------
# 8. Page Content
# -------------------------------------------------

# --- DASHBOARD ---
if st.session_state.page == "Dashboard":
    st.title(f"📊 {project_key} Performance Dashboard")
    
    if st.session_state.all_worklogs is None:
        with st.spinner("Fetching Jira data..."):
            st.session_state.all_worklogs = load_all_worklogs(client)

    df = st.session_state.all_worklogs
    if df.empty:
        st.info("No worklogs found to display.")
    else:
        df["Date"] = pd.to_datetime(df["Date"])
        
        c1, c2 = st.columns(2)
        with c1:
            fig_issue = px.bar(df.groupby("Issue")["Hours"].sum().reset_index(), x="Issue", y="Hours", title="Time by Issue", color="Issue")
            st.plotly_chart(fig_issue, use_container_width=True)
        with c2:
            fig_daily = px.line(df.groupby("Date")["Hours"].sum().reset_index(), x="Date", y="Hours", title="Daily Velocity")
            st.plotly_chart(fig_daily, use_container_width=True)

# --- CREATE ISSUES ---
elif st.session_state.page == "Issues":
    st.title("🐞 Create New Issue")
    
    if st.session_state.projects is None:
        st.session_state.projects = client.get_projects()
    
    project_map = {f"{p['name']} ({p['key']})": p["key"] for p in st.session_state.projects}
    
    # Pre-select the current project if we detected it via the bridge
    default_index = 0
    if project_key != "Global":
        for i, (name, key) in enumerate(project_map.items()):
            if key == project_key:
                default_index = i
                break

    selected_p = st.selectbox("Project", list(project_map.keys()), index=default_index)
    itype = st.selectbox("Type", ["Task", "Bug", "Story", "Epic"])
    summary = st.text_input("Summary")
    desc = st.text_area("Description")
    
    if st.button("Create Issue", type="primary"):
        if summary:
            new_issue = client.create_issue(project_key=project_map[selected_p], summary=summary, description=desc, issue_type=itype)
            st.success(f"Issue Created: {new_issue['key']}")
        else:
            st.error("Summary is required.")

# --- ADD WORKLOGS ---
elif st.session_state.page == "Worklogs":
    st.title("📝 Log Your Work")
    st.session_state.issues = client.get_my_issues()
    
    for issue in st.session_state.issues:
        with st.expander(f"{issue['key']}: {issue['fields']['summary']}"):
            with st.form(key=f"wl_{issue['key']}"):
                d = st.date_input("Date", date.today())
                t = st.time_input("Start Time")
                ts = st.text_input("Time Spent", "1h")
                comment = st.text_area("Comment")
                if st.form_submit_button("Submit Worklog"):
                    iso = format_started_iso(d, t)
                    client.add_worklog(issue['key'], ts, comment, iso)
                    st.success("Logged!")
                    st.session_state.all_worklogs = None # Force refresh

# --- REPORTS ---
elif st.session_state.page == "Reports":
    st.title("📈 Worklog Reports")
    if st.button("Refresh Report Data"):
        st.session_state.report_df = load_all_worklogs(client)
    
    df = st.session_state.report_df
    if not df.empty:
        st.data_editor(df, use_container_width=True, hide_index=True)
        st.download_button("Download CSV", df.to_csv(index=False), "worklogs.csv", "text/csv")
    else:
        st.info("Load data to see the report.")

# --- AI ASSISTANT ---
elif st.session_state.page == "AI Assistant":
    render_ai_assistant(client, lambda: load_all_worklogs(client))
