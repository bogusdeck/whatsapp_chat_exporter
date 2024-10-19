from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import zipfile
from .utils import parse_chat

app = FastAPI()

# Configure templates
templates = Jinja2Templates(directory="templates")
UPLOAD_FOLDER = Path("chat_uploads")
UPLOAD_FOLDER.mkdir(exist_ok=True)

@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <html>
        <body>
            <form action="/upload" enctype="multipart/form-data" method="post">
                <input name="file" type="file" />
                <input type="submit" />
            </form>
        </body>
    </html>
    """

@app.post("/upload")
async def upload_chat(file: UploadFile = File(...)):
    chat_zip = UPLOAD_FOLDER / file.filename

    # Save the uploaded ZIP file
    with chat_zip.open("wb") as buffer:
        buffer.write(await file.read())

    # Extract ZIP and parse the chat
    extracted_folder = chat_zip.with_suffix('')
    with zipfile.ZipFile(chat_zip, 'r') as zip_ref:
        zip_ref.extractall(extracted_folder)
 
    chat_file = next(extracted_folder.glob("*.txt"))  
    messages = parse_chat(chat_file)  

    return templates.TemplateResponse("chat.html", {"request": {}, "messages": messages})

