import streamlit as st
import app.pages as pages
import app.utils as utils

def render(key_prefix: str = "reader"):
    # App title
    pages.show_home()
    pages.show_sidebar()

    st.header("⚙️Settings")
    # Display Azure authentication information
    st.write(":blue[👤 **User Information**]")

    with st.expander("Authentication Details"):
        # Get request headers using Streamlit's context
        headers = st.context.headers
        
        if headers:
            # Display user information
            user_name = headers.get('X-MS-CLIENT-PRINCIPAL-NAME', 'Not available')
            user_id = headers.get('X-MS-CLIENT-PRINCIPAL-ID', 'Not available')
            st.write(f"User Name: {user_name}")
            st.write(f"User ID: {user_id}")
            
            # Display all headers
            # st.write("**All Request Headers:**")
            # st.write(headers)
        else:
            st.warning("No authentication headers found. Make sure you're running this app in Azure App Service with authentication enabled.")

    # Get all styles
    styles = utils.get_styles()

    if styles:
        # Create a selection box for styles
        style_names = [style["name"] for style in styles if style.get("name")]
        if style_names:
            selected_style = st.selectbox(":blue[**Select a style to delete:**]", style_names)
            
            # Get the selected style's full details
            selected_style_data = next((style for style in styles if style["name"] == selected_style), None)
            
            if selected_style_data:            
                # Delete button
                if st.button(f":blue[**Delete '{selected_style}'**]"):
                    try:
                        utils.styles_container.delete_item(
                            item=selected_style_data["id"], 
                            partition_key=selected_style_data["style"]
                        )
                        st.success(f"Style '{selected_style}' has been deleted successfully!")
                    except Exception as e:
                        st.error(f"An error occurred while deleting the style: {str(e)}")
        else:
            st.info("No named styles found in the database.")
    else:
        st.info("No styles found in the database.")