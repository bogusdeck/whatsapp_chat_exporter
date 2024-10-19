from fastapi import FastAPI, File, UploadFile, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import zipfile
import re
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# Initialize Firebase Admin SDK with the credentials from environment variables
cred = credentials.Certificate({
    "type": "service_account",
    "project_id": os.getenv("FIREBASE_PROJECT_ID"),
    "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),  # Ensure to format your private key correctly
    "private_key": os.getenv("FIREBASE_PRIVATE_KEY").replace("\\n", "\n"),
    "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
    "client_id": os.getenv("FIREBASE_CLIENT_ID"),
    "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
    "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_CERT_URL"),
    "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_CERT_URL"),
})

firebase_admin.initialize_app(cred)
db = firestore.client()

# Configure templates
templates = Jinja2Templates(directory="templates")
UPLOAD_FOLDER = Path("chat_uploads")
UPLOAD_FOLDER.mkdir(exist_ok=True)

# Mount static directories
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

    with chat_zip.open("wb") as buffer:
        buffer.write(await file.read())

    extracted_folder = chat_zip.with_suffix('')
    with zipfile.ZipFile(chat_zip, 'r') as zip_ref:
        zip_ref.extractall(extracted_folder)

    chat_file = next(extracted_folder.glob("*.txt"), None)
    if not chat_file:
        return {"error": "No chat file found in the uploaded ZIP."}

    messages = parse_chat(chat_file)
    
    # Store messages in Firebase
    for msg in messages:
        db.collection("whatsapp_chats").add({
            "timestamp": msg["timestamp"],
            "sender": msg["sender"],
            "message": msg["message"],
            "media": msg["media"]
        })

    return templates.TemplateResponse("chat.html", {"request": request})

@app.get("/messages")
async def get_messages(offset: int = 0, limit: int = 25):
    # Retrieve messages from Firestore sorted by timestamp
    messages_ref = db.collection("whatsapp_chats").order_by("timestamp", direction=firestore.Query.DESCENDING).offset(offset).limit(limit)
    messages = messages_ref.stream()

    messages_chunk = []
    for msg in messages:
        messages_chunk.append(msg.to_dict())

    return JSONResponse({"messages": messages_chunk})

def parse_chat(chat_file):
    pattern = r"\[(\d{1,2}/\d{1,2}/\d{2,4}), (\d{1,2}:\d{1,2}:\d{1,2})(?:\s*|\u202F)?(AM|PM)?\] ([^:]+): (.+)"
    messages = []

    try:
        with open(chat_file, 'r', encoding='utf-8-sig') as f:
            for line in f:
                match = re.match(pattern, line)
                if match:
                    date, time, am_pm, sender, message = match.groups()

                    try:
                        timestamp = datetime.strptime(
                            f"{date} {time} {am_pm}".strip(), 
                            "%d/%m/%y %I:%M:%S %p" if am_pm else "%d/%m/%y %H:%M:%S"
                        )
                    except ValueError:
                        print(f"Failed to parse: {date} {time} {am_pm}")
                        continue

                    sender = "You" if sender == "." else sender.strip()

                    messages.append({
                        "timestamp": timestamp,
                        "sender": sender,
                        "message": message.strip(),
                        "media": None,
                    })
                elif "<attached:" in line:
                    media_file = line.split("<attached:")[1].strip(">\n").strip()
                    if messages:
                        messages[-1]["media"] = media_file

    except FileNotFoundError:
        print(f"Error: The file {chat_file} was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

    return sorted(messages, key=lambda x: x["timestamp"])
