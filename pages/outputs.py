import streamlit as st
import app.pages as pages
import app.utils as utils

def render(key_prefix: str = "reader"):
    # App title
    pages.show_home()
    pages.show_sidebar()

    st.header("📰Generated Outputs")

    # Display the generated outputs
    with st.spinner("Processing..."):
        utils.get_outputs()
