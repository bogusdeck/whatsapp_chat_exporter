import os
from fastapi import FastAPI, File, UploadFile, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import zipfile
import datetime
import shutil
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore, storage
from .utils import parse_chat
from fastapi.staticfiles import StaticFiles

# Load environment variables
load_dotenv()

# Initialize Firebase Admin SDK
service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")
if not service_account_path or not Path(service_account_path).is_file():
    raise FileNotFoundError("Service account key JSON not found. Check the path in your .env file.")

cred = credentials.Certificate(service_account_path)
firebase_admin.initialize_app(cred, {
    "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET")
})

# Initialize Firestore and Storage clients
db = firestore.client()
bucket = storage.bucket()

app = FastAPI()

# Configure templates and upload folder
templates = Jinja2Templates(directory="templates")
UPLOAD_FOLDER = Path("chat_uploads")
UPLOAD_FOLDER.mkdir(exist_ok=True)

# Mount static directories
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def home() -> HTMLResponse:
    """Render the home page with the upload form."""
    return """
    <html>
        <body>
            <form action="/upload" enctype="multipart/form-data" method="post">
                <input name="file" type="file" required />
                <input type="submit" />
            </form>
        </body>
    </html>
    """

@app.post("/upload")
async def upload_chat(file: UploadFile = File(...)):
    """Handle chat file uploads."""
    chat_zip = UPLOAD_FOLDER / file.filename

    # Save the uploaded ZIP file
    with chat_zip.open("wb") as buffer:
        buffer.write(await file.read())

    # Extract the ZIP file
    extracted_folder = chat_zip.with_suffix('')
    with zipfile.ZipFile(chat_zip, 'r') as zip_ref:
        zip_ref.extractall(extracted_folder)

    # Locate the chat file (first .txt file found)
    chat_file = next(extracted_folder.glob("*.txt"), None)
    if not chat_file:
        raise HTTPException(status_code=400, detail="No chat file found in the uploaded ZIP.")

    # Parse chat messages
    messages = parse_chat(chat_file)

    # Upload media files to Firebase Storage
    media_mapping = await upload_media_to_storage(extracted_folder)

    # Store messages in Firestore with media URLs
    store_messages_in_firestore(messages, media_mapping)

    # Clean up: delete extracted folder and uploaded ZIP
    shutil.rmtree(extracted_folder)
    chat_zip.unlink()

    # Redirect to chat display page
    return RedirectResponse(url="/chat", status_code=303)

async def upload_media_to_storage(extracted_folder: Path):
    """Upload media files to Firebase Storage and map URLs."""
    media_mapping = {}

    for media_file in extracted_folder.glob("*"):
        # Create a unique name to avoid conflicts
        blob_name = f"{datetime.datetime.utcnow().timestamp()}_{media_file.name}"
        blob = bucket.blob(blob_name)

        # Upload the file
        blob.upload_from_filename(str(media_file))

        # Optionally, make the file public
        blob.make_public()

        # Store the public URL in the mapping
        media_mapping[media_file.name] = blob.public_url

    return media_mapping

def store_messages_in_firestore(messages, media_mapping):
    """Store chat messages in Firestore with media URLs."""
    messages_ref = db.collection('whatsapp_messages')

    for message in messages:
        # Ensure timestamp is in ISO format
        if isinstance(message['timestamp'], datetime.datetime):
            message['timestamp'] = message['timestamp'].isoformat()

        # Attach media URL if present
        if message.get("media") in media_mapping:
            message["media_url"] = media_mapping[message["media"]]

        # Add each message as a new document
        messages_ref.add(message)

@app.get("/chat", response_class=HTMLResponse)
async def display_chat(request: Request):
    """Display chat messages from Firestore ordered by timestamp."""
    messages_ref = db.collection('whatsapp_messages').order_by('timestamp')
    docs = messages_ref.stream()

    # Convert Firestore data to a list of messages
    messages = [
        {
            "timestamp": doc.to_dict().get("timestamp"),
            "sender": doc.to_dict().get("sender"),
            "message": doc.to_dict().get("message"),
            "media_url": doc.to_dict().get("media_url")
        }
        for doc in docs
    ]
    print("Retrieved messages:", messages)
    
    return templates.TemplateResponse("chat.html", {"request": request, "messages": messages})
