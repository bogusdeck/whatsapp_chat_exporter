import os
import hashlib
from fastapi import FastAPI, File, UploadFile, Request, HTTPException, BackgroundTasks, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import zipfile
import datetime
import shutil
from typing import List, Dict, Tuple
from firebase_admin import credentials, firestore, storage, initialize_app
import logging
from dotenv import load_dotenv
from starlette.middleware.sessions import SessionMiddleware
from .utils import parse_chat
from passlib.context import CryptContext
from datetime import timedelta

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FirebaseClient:
    def __init__(self):
        self.init_firebase()
        self.db = firestore.client()
        self.bucket = storage.bucket()

    def init_firebase(self):
        service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")
        if not service_account_path or not Path(service_account_path).is_file():
            raise FileNotFoundError("Firebase service account key not found")
        
        cred = credentials.Certificate(service_account_path)
        initialize_app(cred, {
            "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET")
        })

class ChatProcessor:
    def __init__(self, firebase_client):
        self.firebase = firebase_client
        self.upload_folder = Path("chat_uploads")
        self.upload_folder.mkdir(exist_ok=True)

    async def process_chat_file(self, file: UploadFile) -> Tuple[List[Dict], int]:
        """Process uploaded chat ZIP file and return parsed messages."""
        chat_zip = self.upload_folder / file.filename
        try:
            await self._save_and_extract_zip(file, chat_zip)
            extracted_folder = chat_zip.with_suffix('')
            chat_file = next(extracted_folder.glob("*.txt"), None)
            
            if not chat_file:
                raise HTTPException(status_code=400, detail="No chat file found in ZIP")
            
            messages, count = await self._parse_and_process_messages(chat_file, extracted_folder)
            return messages, count
            
        finally:
            self._cleanup_files(chat_zip)

    async def _save_and_extract_zip(self, file: UploadFile, chat_zip: Path):
        """Save and extract the uploaded ZIP file."""
        try:
            content = await file.read()
            chat_zip.write_bytes(content)
            
            with zipfile.ZipFile(chat_zip, 'r') as zip_ref:
                zip_ref.extractall(chat_zip.with_suffix(''))
                
        except Exception as e:
            logger.error(f"Error processing ZIP file: {e}")
            raise HTTPException(status_code=400, detail="Invalid ZIP file")

    async def _parse_and_process_messages(self, chat_file: Path, extracted_folder: Path) -> Tuple[List[Dict], int]:
        """Parse chat messages and process media files."""
        messages, count = parse_chat(chat_file)
        
        media_mapping = await self._upload_media_files(extracted_folder)
        
        for msg in messages:
            if msg.media:
                msg.media_urls = [media_mapping.get(media) for media in msg.media]
                
        await self._store_messages(messages)
        
        return messages, count

    async def _upload_media_files(self, folder: Path) -> Dict[str, str]:
        """Upload media files to Firebase Storage."""
        media_mapping = {}
        
        for media_file in folder.glob("*"):
            if media_file.suffix.lower() in {'.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mp3'}:
                blob_name = f"{datetime.datetime.utcnow().timestamp()}_{media_file.name}"
                blob = self.firebase.bucket.blob(blob_name)
                
                try:
                    blob.upload_from_filename(str(media_file))
                    blob.make_public()
                    media_mapping[media_file.name] = blob.public_url
                except Exception as e:
                    logger.error(f"Failed to upload {media_file}: {e}")
                    
        return media_mapping

    async def _store_messages(self, messages: List[Dict]):
        """Store messages in Firestore with deduplication and msg_no field."""
        batch = self.firebase.db.batch()
        messages_ref = self.firebase.db.collection('whatsapp_messages')

        messages.sort(key=lambda msg: msg['timestamp'])

        for idx, msg in enumerate(messages, start=1):
            doc_id = self._generate_message_id(msg)

            if not self._message_exists(doc_id):
                msg["msg_no"] = idx
                doc_ref = messages_ref.document(doc_id)
                batch.set(doc_ref, msg)

        batch.commit()

    def _message_exists(self, doc_id: str) -> bool:
        """Check if a message already exists in Firestore."""
        doc_ref = self.firebase.db.collection('whatsapp_messages').document(doc_id)
        doc_snapshot = doc_ref.get()  
        return doc_snapshot.exists

    @staticmethod
    def _generate_message_id(msg: Dict) -> str:
        """Generate a unique message ID based on message content and timestamp."""
        unique_str = f"{msg['timestamp']}_{msg['sender']}_{msg['message']}"
        return hashlib.md5(unique_str.encode()).hexdigest()

    @staticmethod
    def _cleanup_files(chat_zip: Path):
        """Clean up temporary files."""
        try:
            if chat_zip.exists():
                shutil.rmtree(chat_zip.with_suffix(''), ignore_errors=True)
                chat_zip.unlink()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY"))
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

firebase_client = FirebaseClient()
chat_processor = ChatProcessor(firebase_client)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def check_password(entered_password: str, stored_password_hash: str) -> bool:
    return pwd_context.verify(entered_password, stored_password_hash)

async def require_authentication(request: Request):
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=403, detail="Please log in to access this page")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    if not request.session.get("authenticated"):
        return RedirectResponse(url="/passwordcheck")
    return RedirectResponse(url="/chat")

@app.get("/passwordcheck", response_class=HTMLResponse)
async def password_check(request: Request):
    """Render the password check page."""
    return templates.TemplateResponse("password_check.html", {
        "request": request,
        "title": "Enter Password"
    })

@app.get("/photos", response_class=HTMLResponse, dependencies=[Depends(require_authentication)])
async def photos_view(request: Request):
    bucket = storage.bucket()
    blobs = bucket.list_blobs()  
    photo_urls = [blob.generate_signed_url(expiration=timedelta(hours=1)) for blob in blobs]
    return templates.TemplateResponse("photos.html", {"request": request, "photo_urls": photo_urls})

@app.get("/logout")
async def logout(response: RedirectResponse):
    response.delete_cookie("session", path="/")  
    response.headers["Location"] = "/"  
    return response

@app.post("/passwordcheck")
async def password_check_post(request: Request, password: str = Form(...)):
    stored_password_hash = firebase_client.db.collection("passwords").document("user_password").get().to_dict().get("password_hash")
    
    if stored_password_hash and check_password(password, stored_password_hash):
        request.session["authenticated"] = True
        return RedirectResponse(url="/chat", status_code=303)
    else:
        raise HTTPException(status_code=401, detail="Incorrect password")

@app.post("/upload", dependencies=[Depends(require_authentication)])
async def upload_chat(background_tasks: BackgroundTasks, file: UploadFile = File(...)) -> RedirectResponse:
    try:
        messages, count = await chat_processor.process_chat_file(file)
        logger.info(f"Processed {count} messages successfully")
        return RedirectResponse(url=f"/chat?count={count}", status_code=303)
        
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process chat file")

@app.get("/chat", response_class=HTMLResponse, dependencies=[Depends(require_authentication)])
async def display_chat(request: Request, count: int = 0, start_after: int = None, start_before: int = None):
    messages_ref = firebase_client.db.collection("whatsapp_messages").order_by("msg_no", direction=firestore.Query.ASCENDING)

    if start_after is not None:
        messages_ref = messages_ref.start_after({"msg_no": start_after})

    if start_before is not None:
        messages_ref = messages_ref.end_before({"msg_no": start_before})

    messages_stream = messages_ref.limit(20).stream()
    messages = [message.to_dict() for message in messages_stream]

    next_start_after = messages[-1]["msg_no"] if messages else None
    prev_start_before = messages[0]["msg_no"] if messages else None

    messages.reverse()

    return templates.TemplateResponse("chat.html", {
        "request": request,
        "messages": messages,
        "next_start_after": next_start_after,
        "prev_start_before": prev_start_before,
    })

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "error": exc.detail},
        status_code=exc.status_code
    )

