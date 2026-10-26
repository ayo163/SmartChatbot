import streamlit as st
from api_utils import upload_document, list_documents, delete_document

def display_sidebar():
    #sidebar:Model selection
    model_options = ["gpt-4-0", "gpt-4-0-mini"]
    st.sidebar.selectbox("Select Model", options = model_options, dey="model")

    #Sidebar: upload Document
    st.sidebar.header("upload document")
    uploaded_file = st.sidebar.file_uploader("Choose a file", type=["pdf", "docx","html"])
    if uploaded_file is not None:
        if st.sidebar.button("upload"):
            with st.pinner("Uploading..."):
                upload_response = upload_document(uploaded_file)
                if upload_response:
                    st.sidebar.success(f"File '{uploaded_file.name}' uploaded successfully with ID {upload_response['file_id']}.")
                    st.session_state.documents = list_documents() 

#Sidebar list documents
st.sidebar.header("Uploaded Documents")
if st.sidebar.button("Refresh Document List"):
    with st.spinner("Refreshing..."):
        st.session_state.documents = list_documents()


#Initialize document list if not present
if "documents" not in st.session_state:
    st.session_state.documents = list_documents()

documents = st.session_state.documents
if documents: 
    for doc in documents:
        