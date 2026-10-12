from fastapi import FastAPI, File, UploadFile, HTTPException
from pydantic_models import QueryInput, QueryResponse, DocumentInfo, DeleteFileRequest
from langchain_utils import get_rag_chain
from db_utils import insert_application_logs, get_chat_history, get_all_documents, insert_document_record, delete_document_record
from chroma_utils import index_document_to_chroma, delete_doc_from_chroma
import os
import uuid
import logging
import shutil
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from urllib.parse import urlencode
from fastapi import Request
from fastapi.responses import RedirectResponse
import os
import shutil
import tempfile
from fastapi import File, UploadFile, HTTPException


load_dotenv()

# Set up logging
logging.basicConfig(filename='app.log', level=logging.INFO)

# Initialize FastAPI app
app = FastAPI()

# Setup Jinja2 templates directory
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Route 1: Render the homepage form
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    # return templates.TemplateResponse("index.html", {"request": request, "result": None})
    return templates.TemplateResponse(request=request,  name="index.html", context={"result": None})


#for chat endpoint
@app.post("/chat", response_class=HTMLResponse)
def chat(request: Request, question: str = Form(...),
    session_id: str = Form(default=None), model: str = Form(default="gpt-4o-mini")
):
    session_id = session_id or str(uuid.uuid4())

    logging.info( f"Session ID: {session_id},"
        f"User Query: {question}, Model: {model}"
    )

    chat_history = get_chat_history(session_id)
    rag_chain = get_rag_chain(model)

    answer = rag_chain.invoke({
        "input": question, "chat_history": chat_history
    })["answer"]

    insert_application_logs(
        session_id, question, answer, model
    )

    logging.info(
        f"Session ID: {session_id}, AI Response: {answer}"
    )

    return templates.TemplateResponse( request=request,name="index.html",
             context={"question": question, "result": answer, "session_id": session_id,
            "model": model
        }
    )

# for the upload file

@app.post("/upload-doc")
def upload_and_index_document(
    request: Request,
    file: UploadFile = File(...)
):
    allowed_extensions = {".pdf", ".docx", ".html"}

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Please select a file to upload."
        )

    file_extension = os.path.splitext(file.filename)[1].lower()

    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Allowed types are: .pdf, .docx, .html"
        )

    temp_file_path = None
    file_id = None

    try:
        # Create a temporary file
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=file_extension
        ) as temp_file:

            temp_file_path = temp_file.name

            shutil.copyfileobj(file.file, temp_file)

        # Save document information to database
        file_id = insert_document_record(file.filename)

        # Index document in ChromaDB
        success = index_document_to_chroma(
            temp_file_path,
            file_id
        )

        if not success:
            delete_document_record(file_id)
            file_id = None

            raise HTTPException(
                status_code=500,
                detail=f"Failed to index {file.filename}."
            )

        # Return JSON response
        return {
            "message": f"{file.filename} uploaded and indexed successfully.",
            "file_id": file_id
        }

    except HTTPException:
        raise

    except Exception as exc:
        if file_id is not None:
            delete_document_record(file_id)

        raise HTTPException(
            status_code=500,
            detail="An error occurred while uploading or indexing the document."
        ) from exc

    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)

        file.file.close()



# list documents endpoint
@app.get("/list-docs", response_model=list[DocumentInfo])
def list_documents():
    return get_all_documents()

# Delete document endpoint

@app.post("/delete-doc")
def delete_document(request: DeleteFileRequest):
    chroma_delete_success = delete_doc_from_chroma(request.file_id)

    if chroma_delete_success:
        db_delete_success = delete_document_record(request.file_id)
        if db_delete_success:
            return {"message": f"Successfully deleted document with file_id: {request.file_id} from the system."}
        else:
            return {"error": f"Deleted from Chroma but failed to delete document with file_id {request.file_id} from the database."}
    else:
        return {"error": f"Failed to delete document with file_id: {request.file_id} from Chroma."}
