import time
import streamlit as st
import pandas as pd
import openai

# -------------------------------------------------
# AI ASSISTANT RENDER FUNCTION
# -------------------------------------------------
def render_ai_assistant(client, load_all_worklogs):
    st.title("🤖 AI Assistant (Advanced Jira Analytics)")

    # ---------------- Load worklogs (cached) ----------------
    if "all_worklogs" not in st.session_state or st.session_state.all_worklogs is None:
        with st.spinner("Loading worklogs..."):
            st.session_state.all_worklogs = load_all_worklogs()

    df = st.session_state.all_worklogs

    if df.empty:
        st.info("No worklogs available for AI analysis.")
        return

    # ---------------- Build AI context ----------------
    def build_context(df: pd.DataFrame) -> str:
        summary = []

        for project, hours in df.groupby("Project")["Hours"].sum().items():
            summary.append(f"Project: {project} — Total Hours: {round(hours, 2)}")

        for issue, hours in df.groupby("Issue")["Hours"].sum().items():
            summary.append(f"Issue: {issue} — Total Hours: {round(hours, 2)}")

        for author, hours in df.groupby("Author")["Hours"].sum().items():
            summary.append(f"Author: {author} — Total Hours: {round(hours, 2)}")

        return "\n".join(summary)

    # ---------------- User question ------------------
    question = st.text_input(
        "Ask anything about Jira 👇",
        placeholder=(
            "Examples: Who worked the most? "
            "Compare project hours. "
            "List issues with highest effort."
        )
    )

    # ---------------- OpenAI API key ----------------
    api_key = None
    try:
        api_key = st.secrets["OPENAI_API_KEY"]
    except Exception:
        api_key = st.text_input("Enter OpenAI API Key", type="password")

    if api_key:
        openai.api_key = api_key

    # ---------------- Run AI ----------------
    if st.button("🚀 Ask AI") and api_key and question:
        with st.spinner("AI is thinking..."):
            progress = st.progress(0)
            for i in range(100):
                time.sleep(0.01)
                progress.progress(i + 1)

            context = build_context(df)

            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert Jira analytics assistant."
                    },
                    {
                        "role": "user",
                        "content": f"DATA:\n{context}\n\nQUESTION:\n{question}"
                    }
                ],
                temperature=0.3
            )

            st.success("✅ AI Answer")
            st.markdown(response.choices[0].message.content)

   