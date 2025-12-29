import time
import streamlit as st
import pandas as pd
import plotly.express as px
import openai

# =====================================================
# MAIN RENDER FUNCTION
# =====================================================
def render_ai_assistant(client, load_all_worklogs):

    st.header("🤖 AI Assistant – Jira Analytics")

    # -------------------------------------------------
    # Load worklogs safely
    # -------------------------------------------------
    if st.session_state.get("all_worklogs") is None:
        with st.spinner("Loading Jira worklogs..."):
            data = load_all_worklogs()

            # ✅ GUARANTEE DataFrame
            if data is None:
                data = pd.DataFrame(
                    columns=["Project", "Issue", "Date", "Hours", "Author"]
                )

            st.session_state.all_worklogs = data

    df = st.session_state.all_worklogs

    if df.empty:
        st.warning("No Jira worklogs available for analysis.")
        return

    df = df.copy()

    # -------------------------------------------------
    # Initialize session state
    # -------------------------------------------------
    if "ai_question" not in st.session_state:
        st.session_state.ai_question = ""

    if "run_ai" not in st.session_state:
        st.session_state.run_ai = False

    # -------------------------------------------------
    # AI Suggestions (Static + Smart)
    # -------------------------------------------------
    st.markdown("### 🔮 Try asking one of these:")

    suggestions = [
        "Show total hours per project",
        "Who logged the most hours?",
        "Show a bar chart of hours by author",
        "Which issues took the most effort?",
        "Compare project workloads",
        "Show hours trend by date"
    ]

    cols = st.columns(3)
    for i, prompt in enumerate(suggestions):
        if cols[i % 3].button(prompt):
            st.session_state.ai_question = prompt
            st.session_state.run_ai = True

    # -------------------------------------------------
    # Question Input
    # -------------------------------------------------
    question = st.text_input(
        "Ask anything about Jira 👇",
        key="ai_question",
        placeholder="e.g. Show a chart of hours per project"
    )

    # -------------------------------------------------
    # OpenAI API Key
    # -------------------------------------------------
    api_key = st.secrets.get("OPENAI_API_KEY", None)
    if not api_key:
        api_key = st.text_input("Enter OpenAI API Key", type="password")

    if not api_key:
        st.info("Please provide OpenAI API key.")
        return

    openai.api_key = api_key

    # -------------------------------------------------
    # Run AI
    # -------------------------------------------------
    if st.button("🚀 Ask AI") or st.session_state.run_ai:

        st.session_state.run_ai = False

        with st.spinner("AI is analyzing Jira data..."):
            time.sleep(0.3)

            # ------------------------------
            # Natural language → chart logic
            # ------------------------------
            q = question.lower()

            if "chart" in q or "graph" in q or "bar" in q:

                if "project" in q:
                    chart_df = df.groupby("Project")["Hours"].sum().reset_index()
                    fig = px.bar(chart_df, x="Project", y="Hours",
                                 title="Hours by Project")
                    st.plotly_chart(fig, use_container_width=True)
                    return

                if "author" in q or "user" in q:
                    chart_df = df.groupby("Author")["Hours"].sum().reset_index()
                    fig = px.bar(chart_df, x="Author", y="Hours",
                                 title="Hours by Author")
                    st.plotly_chart(fig, use_container_width=True)
                    return

                if "date" in q or "trend" in q:
                    chart_df = df.groupby("Date")["Hours"].sum().reset_index()
                    fig = px.line(chart_df, x="Date", y="Hours",
                                  title="Worklog Trend Over Time")
                    st.plotly_chart(fig, use_container_width=True)
                    return

            # ------------------------------
            # Build AI Context
            # ------------------------------
            summary = []
            for project, hours in df.groupby("Project")["Hours"].sum().items():
                summary.append(f"Project {project}: {round(hours, 2)} hours")

            for author, hours in df.groupby("Author")["Hours"].sum().items():
                summary.append(f"Author {author}: {round(hours, 2)} hours")

            context = "\n".join(summary)

            # ------------------------------
            # OpenAI Call
            # ------------------------------
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert Jira analytics assistant."
                    },
                    {
                        "role": "user",
                        "content": f"""
DATA:
{context}

QUESTION:
{question}
"""
                    }
                ],
                temperature=0.3
            )

            st.success("✅ AI Answer")
            st.markdown(response.choices[0].message.content)

