from fastapi import FastAPI, File, UploadFile, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import zipfile
from .utils import parse_chat
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Configure templates
templates = Jinja2Templates(directory="templates")
UPLOAD_FOLDER = Path("chat_uploads")
UPLOAD_FOLDER.mkdir(exist_ok=True)

# Mount static directories
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/chat_uploads", StaticFiles(directory="chat_uploads"), name="chat_uploads")

@app.get("/", response_class=HTMLResponse)
async def home() -> HTMLResponse:
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
async def upload_chat(request: Request, file: UploadFile = File(...)):
    chat_zip = UPLOAD_FOLDER / file.filename

    # Save the uploaded ZIP file
    with chat_zip.open("wb") as buffer:
        buffer.write(await file.read())

    # Extract ZIP and parse the chat
    extracted_folder = chat_zip.with_suffix('')
    with zipfile.ZipFile(chat_zip, 'r') as zip_ref:
        zip_ref.extractall(extracted_folder)

    print(f"Extracted folder: {extracted_folder}")

    # Find the first text file in the extracted folder
    chat_files = list(extracted_folder.glob("*.txt"))
    if not chat_files:
        return {"error": "No chat file found in the uploaded ZIP."}

    chat_file = chat_files[0]  # You can modify this to handle multiple files if needed
    print(f"Chat file found: {chat_file}")

    messages = parse_chat(chat_file)

    print(messages)

    # Pass the actual request object to the template
    return templates.TemplateResponse("chat.html", {"request": request, "messages": messages})
