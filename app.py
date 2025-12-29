import streamlit as st
import base64
import pandas as pd
import matplotlib.pyplot as plt

from datetime import datetime, date
from dateutil.tz import tzlocal
from jira_client import JiraClient
import plotly.express as px

from ai_assistant import render_ai_assistant

st.set_page_config(
    page_title="Innodata Jira Dashboard",
    layout="wide"
)


if "report_df" not in st.session_state:
    st.session_state.report_df = pd.DataFrame()
# -------------------------------------------------
# Page config
# -------------------------------------------------



def load_image_base64(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()



# -------------------------------------------------
# Utils
# -------------------------------------------------
def encode(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode()

def decode(s: str) -> str:
    return base64.urlsafe_b64decode(s.encode()).decode()

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

# -------------------------------------------------
# Session defaults (SAFE)
# -------------------------------------------------
defaults = {
    "base_url": "",
    "email": "",
    "api_token": "",
    "client": None,
    "logged_in": False,
    "issues": [],
    "all_worklogs": None,
    "report_df": None,
    "page": "Dashboard",
    "edit_worklog": None,
    "delete_worklog": None

}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


#-------------- SESSION STATE ------------

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "client" not in st.session_state:
    st.session_state.client = None

if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

if "user_name" not in st.session_state:
    st.session_state.user_name = ""

if "edit_worklog" not in st.session_state:
    st.session_state.edit_worklog = None

if "delete_worklog" not in st.session_state:
    st.session_state.delete_worklog = None

if "selected_worklog_id" not in st.session_state:
    st.session_state.selected_worklog_id = None



# --- Replace the old "Auto-login from URL" block with this ---

import streamlit as st
from jira_client import JiraClient

# Initialize session state keys if they don't exist
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# 1. Access Forge Headers
headers = st.context.headers
# Note: In some environments, headers are lowercase
forge_auth = headers.get("authorization") 

# 2. Auto-login Logic
if not st.session_state.logged_in and forge_auth:
    try:
        # Extract JWT from "Bearer <token>"
        jwt_token = forge_auth.split(" ")[1] if " " in forge_auth else forge_auth
        
        base_url = st.secrets["JIRA_BASE_URL"]
        
        # Initialize JiraClient with JWT
        client = JiraClient(base_url, jwt_token=jwt_token)
        
        # Verify the token works by calling Jira
        me = client.get_myself()

        # Update Session State
        st.session_state.client = client
        st.session_state.logged_in = True
        st.session_state.user_name = me["displayName"]
        st.session_state.base_url = base_url
        
        st.toast(f"Welcome, {me['displayName']}!", icon="👋")
    except Exception as e:
        st.error(f"Forge Auto-login failed: {e}")

# 3. App Routing
if st.session_state.logged_in:
    st.title(f"Dashboard for {st.session_state.user_name}")
    # Your main app logic here...
else:
    st.warning("Please open this app from within a Jira Issue or Dashboard.")


    # ---------------- LOGIN ----------------
    if not st.session_state.logged_in:
        base_url = st.text_input("Jira Base URL")
        email = st.text_input("Email")
        token = st.text_input("API Token", type="password")


        # --------------- Generate Token Link (NEW) ---------------
        # st.markdown(
        #     """
        #     <a href="https://id.atlassian.com/manage-profile/security/api-tokens"
        #     target="_blank"
        #     style="
        #         display: block;
        #         margin-top: 6px;
        #         margin-bottom: 12px;
        #         padding: 8px 12px;
        #         background-color: #1A6173;
        #         color: white;
        #         text-align: center;
        #         border-radius: 6px;
        #         text-decoration: none;
        #         font-weight: 600;
        #     ">
        #     🔑 Generate Jira API Token
        #     </a>
        #     """,
        #     unsafe_allow_html=True
        # )

        login_clicked = st.button("Login", key="login_btn", use_container_width=True)


        if login_clicked:

            try:
                client = JiraClient(
                    base_url.strip(),
                    email.strip(),
                    token.strip()
                )
                me = client.get_myself()

                st.session_state.base_url = base_url
                st.session_state.email = email
                st.session_state.api_token = token
                st.session_state.client = client
                st.session_state.logged_in = True
                st.session_state.user_name = me["displayName"]  # ✅ SET

                st.query_params.update({
                    "logged_in": "true",
                    "base_url": encode(base_url),
                    "email": encode(email),
                    "token": encode(token)
                })

                st.success(f"Logged in as {me['displayName']}")
                st.rerun()

            except Exception as e:
                st.error(f"Login failed: {e}")

    # ---------------- NAVIGATION ----------------
    else:
        # ---------------- USER INFO ----------------
        st.markdown(
            f"""
            <div style="font-weight:600; padding-bottom:18px;">
                👤 {st.session_state.user_name}
            </div>
            """,
            unsafe_allow_html=True
        )

        #st.markdown("### 📌 Navigation")

        # st.markdown(
        #     """
        #     <h3 style="text-align: center;top-margin:5px; margin-bottom: 10px;font-size:25px;">
        #        <u> <b> Navigation</b></u>
        #     </h3>
        #     """,
        #     unsafe_allow_html=True
        # )


        # ---------------- Navigation Buttons ----------------
        def nav_button(label, page_name):
            is_active = st.session_state.page == page_name

            if st.button(
                label,
                use_container_width=True,
                type="primary" if is_active else "secondary"
            ):
                if st.session_state.page != page_name:
                    st.session_state.page = page_name
                    st.rerun()

        nav_button("📊 Dashboard", "Dashboard")
        nav_button("🐞 Issues", "Issues")
        nav_button("📝 Worklogs", "Worklogs")
        nav_button("📈 Reports", "Reports")
        nav_button("🤖 AI Assistant", "AI Assistant")


        st.markdown("---")

        # ---------------- Logout ----------------
        if st.button("🚪 Logout", key="logout_btn", use_container_width=True):
            st.query_params.clear()

            for k in list(st.session_state.keys()):
                del st.session_state[k]

            st.rerun()



# -------------------------------------------------
# Block app if not logged in
# -------------------------------------------------
if not st.session_state.logged_in:
    # Main Hero Section
    st.markdown(
        """
        <div style="text-align: center; padding: 40px 0px;">
            <h1 style="font-size: 3rem; color: #1A6173;">🚀 Jira Worklog Manager</h1>
            <p style="font-size: 1.2rem; color: #555;">
                The ultimate companion for tracking, managing, and analyzing your Jira productivity.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
 
    # Features Grid
    col1, col2, col3 = st.columns(3)
 
    with col1:
        st.markdown("### 📊 Dashboards")
        st.write("Visualize your time spent across different projects and issues with interactive charts.")
       
    with col2:
        st.markdown("### 📝 Easy Logging")
        st.write("Log work instantly against your assigned Jira issues without the complex Jira UI.")
       
    with col3:
        st.markdown("### 🤖 AI Powered")
        st.write("Ask our AI Assistant to analyze your work and help whenever stuck !.")
 
    st.markdown("---")
 
    # Call to Action / Instructions
    c1, c2 = st.columns([2, 1])
    with c1:
        st.info("### 🔐 Get Started")
        st.markdown(
            """
            1. Enter your **Jira Base URL** (e.g., `https://your-company.atlassian.net`).
            2. Provide your **Email used during creation of Jira account**.
            3. Use a **Jira API Token** (not your password).
           
            Use the sidebar on the left to sign in and unlock your dashboard.
            """
        )
   
    with c2:
        st.markdown("### 💡 Pro Tip")
        st.markdown(
            """
            <p style="font-size: 20px; font-weight: 500; line-height: 1.5;">
                You can generate an API token from your Atlassian security settings
                or just click below button.
            </p>
            """,
            unsafe_allow_html=True
        )
        st.markdown(
            """
            <a href="https://id.atlassian.com/manage-profile/security/api-tokens"
            target="_blank"
            style="
                display: block;
                margin-top: 6px;
                margin-bottom: 12px;
                padding: 8px 12px;
                background-color: #1A6173;
                color: white;
                text-align: center;
                border-radius: 6px;
                text-decoration: none;
                font-weight: 600;
            ">
            🔑 Generate Jira API Token
            </a>
            """,
            unsafe_allow_html=True
        )
    # Stop the script here so the rest of the app doesn't run
    st.stop()
client: JiraClient = st.session_state.client
page = st.session_state.page


# -------------------------------------------------
# Common loader
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


if page == "Dashboard":

    # -------------------------------------------------
    # Title
    # -------------------------------------------------



    st.markdown(
        """
        <h1 style='text-align:center;'>📊 Jira Worklog Dashboard</h1>
        <p style='text-align:center; color:gray; font-size:16px;'>
            Interactive analytics across issues, time & users
        </p>
        """,
        unsafe_allow_html=True
    )

    # -------------------------------------------------
    # Load worklogs (cached in session)
    # -------------------------------------------------
    if st.session_state.all_worklogs is None:
        with st.spinner("Loading worklogs..."):
            st.session_state.all_worklogs = load_all_worklogs()

    df = st.session_state.all_worklogs

    if df.empty:
        st.info("No worklogs found")
        st.stop()
    df["Date"] = pd.to_datetime(df["Date"])
    df["Month"] = df["Date"].dt.to_period("M").astype(str)
    df["Year"] = df["Date"].dt.year

    # -------------------------------------------------
    # Chart type selector
    # -------------------------------------------------
    chart_type = st.selectbox(
        "Select Chart Type",
        ["Bar", "Line", "Area", "Pie"]
    )


    # -------------------------------------------------
    # Helper function (NO repetition)
    # -------------------------------------------------

    def load_image_base64(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()

    def build_chart(data, x, y, title, color=None, hover_cols=None):
        if chart_type == "Bar":
            fig = px.bar(
                data,
                x=x,
                y=y,
                color=color,
                hover_data=hover_cols,
                title=title
            )

        elif chart_type == "Line":
            fig = px.line(
                data,
                x=x,
                y=y,
                color=color,
                hover_data=hover_cols,
                title=title
            )

        elif chart_type == "Area":
            fig = px.area(
                data,
                x=x,
                y=y,
                color=color,
                hover_data=hover_cols,
                title=title
            )

        elif chart_type == "Pie":
            fig = px.pie(
                data,
                names=x,
                values=y,
                hover_data=hover_cols,   # ✅ add hover here
                title=title
            )


        return fig


    # -------------------------------------------------
    # Aggregations
    # -------------------------------------------------
    issue_df = issue_df = (df.groupby(["Issue", "Author"], as_index=False)["Hours"].sum())
    day_df = (df.groupby(["Date", "Issue"], as_index=False)["Hours"].sum())
    author_df = (df.groupby("Author", as_index=False)["Hours"].sum())
    monthly_df = df.groupby(["Month", "Issue"], as_index=False)["Hours"].sum()
    yearly_df = df.groupby(["Year", "Issue"], as_index=False)["Hours"].sum()

    # -------------------------------------------------
    # Layout
    # -------------------------------------------------
    col1, col2 = st.columns(2)

    with col1:
        st.plotly_chart(
            build_chart(issue_df, "Issue", "Hours", "🧩 Time by Issue",hover_cols=["Issue", "Author", "Hours"]),
            use_container_width=True
        )

    with col2:
        st.plotly_chart(
                build_chart
                (
                    day_df,
                    "Date",
                    "Hours",
                    "📅 Time by Day",
                    color="Issue",
                    hover_cols=["Issue", "Hours", "Date"]
                ),
            use_container_width=True
        )

    col3, col4 = st.columns(2)
    with col3:
        st.plotly_chart(
            build_chart(
                monthly_df,
                "Month",
                "Hours",
                "📆 Time by Month",
                color="Issue",
                hover_cols=["Month", "Issue", "Hours"]
            ),
        use_container_width=True
        )

    with col4:
        st.plotly_chart(
            build_chart(
                yearly_df,
                "Year",
                "Hours",
                "📈 Time by Year",
                color="Issue",
                hover_cols=["Year", "Issue", "Hours"]
            ),
            use_container_width=True
        )
    # col5 = st.columns(1)
    # with col5:
    left, center, right = st.columns([1, 2, 1])
    with center:
        st.plotly_chart(
            build_chart(author_df, "Author", "Hours", "👤 Time by Author"),
            use_container_width=True
        )


# ---------------------
# ISSUES
# ---------------------

if "projects" not in st.session_state:
    st.session_state.projects = None

elif page == "Issues":
    st.title("🐞 Create Jira Issue")
    if "projects" not in st.session_state:
        st.session_state.projects = None

    if st.session_state.projects is None:
        with st.spinner("Loading projects..."):
            try:
                st.session_state.projects = client.get_projects()
            except Exception as e:
                st.error(f"Failed to load projects: {e}")
                st.stop()

    projects = st.session_state.projects


    project_map = {
        f"{p['name']} ({p['key']})": p["key"]
        for p in projects
    }

    selected_project = st.selectbox(
        "Select Project",
        list(project_map.keys()),
        key="selected_project"
    )

    # ---------------------------
    # Issue Type
    # ---------------------------
    issue_type = st.selectbox(
        "Issue Type",
        ["Task", "Bug", "Story", "Epic"]
    )

    # ---------------------------
    # Common fields
    # ---------------------------
    summary = st.text_input("Summary")
    description = st.text_area("Description")

    # ---------------------------
    # Conditional fields
    # ---------------------------
    epic_name = None
    if issue_type == "Epic":
        epic_name = st.text_input("Epic Name (Required)")

    # ---------------------------
    # Create Issue
    # ---------------------------
    if st.button("Create Issue"):
        if not summary:
            st.warning("Summary is required")
            st.stop()

        if issue_type == "Epic" and not epic_name:
            st.warning("Epic Name is required for Epic issues")
            st.stop()

        with st.spinner("Creating issue..."):
            try:
                issue = client.create_issue(
                    project_key=project_map[selected_project],
                    summary=summary,
                    description=description,
                    issue_type=issue_type,
                    epic_name=epic_name
                )
            except Exception as e:
                st.error(f"Failed to create issue: {e}")
                st.stop()

        st.success(f"✅ Issue created: {issue['key']}")



# -------------------------------------------------
# WORKLOG ENTRY
# -------------------------------------------------
elif page == "Worklogs":
    st.title("📝 Add Worklogs")

    # if st.button("Fetch Issues"):
    st.session_state.issues = client.get_my_issues()

    for issue in st.session_state.issues:
        key = issue["key"]
        summary = issue["fields"]["summary"]

        with st.expander(f"{key} — {summary}"):
            with st.form(f"form_{key}", clear_on_submit=True):
                d = st.date_input("Date", date.today())
                t = st.time_input("Start Time")
                ts = st.text_input("Time Spent", "1h")
                c = st.text_area("Comment")

                if st.form_submit_button("Submit"):
                    iso = format_started_iso(d, t)
                    client.add_worklog(key, ts, c, iso)
                    st.success("Worklog added")

# -------------------------------------------------
# REPORTS
# -------------------------------------------------


elif page == "Reports":
    st.title("📋 Worklog Reports")

    # ---------- LOAD ISSUES ----------
    issues = client.get_my_issues(max_results=200)

    issue_map = {
        "All": None,
        **{f"{i['key']} - {i['fields']['summary']}": i["key"] for i in issues}
    }

    selected = st.selectbox(
        "Select Issue",
        list(issue_map.keys()),
        key="report_issue_select"
    )

    # ---------- LOAD WORKLOGS ----------
    if st.button("Load Worklogs", key="load_report"):
        with st.spinner("⏳ Fetching worklogs from Jira..."):
            rows = []

            for issue in issues:
                if issue_map[selected] and issue["key"] != issue_map[selected]:
                    continue

                project = issue["fields"]["project"]["name"]
                issue_type = issue["fields"].get("issuetype", {}).get("name", "Unknown")

                for wl in client.get_worklogs(issue["key"]):
                    rows.append({
                        "worklog_id": wl["id"],        # internal
                        "issue_key": issue["key"],     # internal
                        "Project Name": project,
                        "Issue Type": issue_type,
                        "Issue": issue["key"],
                        "Date": wl["started"][:10],
                        "Start Time": wl["started"][11:16],
                        "Hours": round(wl["timeSpentSeconds"] / 3600, 2),
                        "Comment": extract_comment(wl.get("comment")),
                        "Author": wl["author"]["displayName"],
                         "User ID": wl["author"].get("accountId", "N/A")
                    })

            if rows:
                df = pd.DataFrame(rows)
                df["Date"] = pd.to_datetime(df["Date"])
                st.session_state.report_df = df
            else:
                st.session_state.report_df = pd.DataFrame()

    # ---------- SHOW REPORT ----------
    if (
        "report_df" in st.session_state
        and isinstance(st.session_state.report_df, pd.DataFrame)
        and not st.session_state.report_df.empty
    ):

        df = st.session_state.report_df.copy()

        st.subheader("🔍 Filters")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            date_range = st.date_input(
                "Date Range",
                value=(df["Date"].min().date(), df["Date"].max().date()),
                key="report_date_filter"
            )

        if not isinstance(date_range, (list, tuple)) or len(date_range) != 2:
            st.warning("⚠️ Please select a valid start and end date.")
            st.stop()

        start_date, end_date = date_range

        with col2:
            project = st.selectbox(
                "Project",
                ["All"] + sorted(df["Project Name"].unique()),
                key="report_project_filter"
            )

        with col3:
            issue_type = st.selectbox(
                "Issue Type",
                ["All"] + sorted(df["Issue Type"].unique()),
                key="report_issue_type_filter"
            )

        with col4:
            author = st.selectbox(
                "Author",
                ["All"] + sorted(df["Author"].unique()),
                key="report_author_filter"
            )

        # ---------- APPLY FILTERS ----------
        filtered_df = df[
            (df["Date"].dt.date >= start_date) &
            (df["Date"].dt.date <= end_date)
        ]

        if project != "All":
            filtered_df = filtered_df[filtered_df["Project Name"] == project]

        if issue_type != "All":
            filtered_df = filtered_df[filtered_df["Issue Type"] == issue_type]

        if author != "All":
            filtered_df = filtered_df[filtered_df["Author"] == author]

        filtered_df = filtered_df.sort_values(
            ["Date", "Start Time"], ascending=False
        )

        # ---------- GRID WITH EDIT & DELETE ----------

        grid_df = filtered_df.copy()
        # grid_df["Edit"] = False
        # grid_df["Delete"] = False

        display_df = grid_df.drop(columns=["worklog_id", "issue_key"])

        edited_df = st.data_editor(
            display_df,
            hide_index=True,
            use_container_width=True,
            # column_config={
            #     "Edit": st.column_config.CheckboxColumn("✏️ Edit"),
            #     "Delete": st.column_config.CheckboxColumn("🗑️ Delete"),
            # },
            key="worklog_grid"
        )

    #     # ---------- EDIT ----------
    #     edit_rows = edited_df[edited_df["Edit"] == True]

    #     if len(edit_rows) == 1:
    #         row = edit_rows.iloc[0]
    #         original = grid_df.loc[row.name]

    #         st.markdown("### ✏️ Edit Worklog")

    #         new_hours = st.number_input(
    #             "Hours",
    #             value=float(original["Hours"]),
    #             step=0.25
    #         )

    #         new_comment = st.text_area(
    #             "Comment",
    #             value=original["Comment"]
    #         )

    #         if st.button("💾 Save Changes"):
    #             client.update_worklog(
    #                 original["issue_key"],
    #                 original["worklog_id"],
    #                 new_hours,
    #                 new_comment
    #             )
    #             st.success("✅ Worklog updated successfully")
    #             st.session_state.report_df = pd.DataFrame()
    #             st.rerun()

    #     elif len(edit_rows) > 1:
    #         st.warning("⚠️ Please select only one row to edit.")

    #     # ---------- DELETE ----------
    #     # ---------- DELETE ----------
    #     delete_rows = edited_df[edited_df["Delete"] == True]

    #     if len(delete_rows) == 1:
    #         row = delete_rows.iloc[0]
    #         original = grid_df.loc[row.name]

    #         st.markdown("### 🗑️ Delete Worklog")
    #         st.warning("⚠️ Are you sure you want to delete this worklog?")

    #         col_yes, col_no = st.columns(2)

    #         with col_yes:
    #             if st.button("✅ Yes, Confirm"):
    #                 client.delete_worklog(
    #                     original["issue_key"],
    #                     original["worklog_id"]
    #                 )
    #                 st.success("🗑️ Worklog deleted successfully")
    #                 st.session_state.report_df = pd.DataFrame()
    #                 st.rerun()

    #         with col_no:
    #             if st.button("❌ No"):
    #                 # Reset delete checkbox state
    #                 st.session_state["worklog_grid"]["edited_rows"] = {}
    #                 st.info("Deletion cancelled")
    #                 st.rerun()


    #     elif len(delete_rows) > 1:
    #         st.warning("⚠️ Please select only one row to delete.")
    else:
        st.info("Click **Load Worklogs** to generate the report.")

elif page == "AI Assistant":
    render_ai_assistant(client,load_all_worklogs)