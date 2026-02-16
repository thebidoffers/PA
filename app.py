import streamlit as st

st.set_page_config(page_title="Prospectus Automation", layout="wide")

st.title("Prospectus Automation (PA)")
st.caption("MVP scaffold for prospectus upload, templates, and auto generation workflows.")

st.sidebar.title("Navigation")
st.sidebar.info(
    "Use the page selector above to open:\n"
    "- YOUR PROSPECTUS\n"
    "- TEMPLATES\n"
    "- AUTO GENERATION"
)

st.markdown(
    """
    ### Welcome
    This app provides a minimal MVP scaffold with three functional sections:
    1. **YOUR PROSPECTUS** for project and document version management.
    2. **TEMPLATES** for DOCX template library management.
    3. **AUTO GENERATION** for input validation and placeholder generation runs.
    """
)
