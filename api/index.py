# api/index.py
import os
import hashlib
from fastapi import FastAPI, File, UploadFile, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import zipfile
import datetime
import shutil
from typing import Dict, List, Tuple
import asyncio
from dataclasses import dataclass
from firebase_admin import credentials, firestore, storage, initialize_app
import logging
from dotenv import load_dotenv
from .utils import parse_chat

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ChatMessage:
    timestamp: datetime.datetime
    sender: str
    message: str
    media: List[str] = None
    media_urls: List[str] = None

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

    async def process_chat_file(self, file: UploadFile) -> Tuple[List[ChatMessage], int]:
        """Process uploaded chat ZIP file and return parsed messages."""
        chat_zip = self.upload_folder / file.filename
        
        try:
            # Save and extract ZIP
            await self._save_and_extract_zip(file, chat_zip)
            
            # Process chat contents
            extracted_folder = chat_zip.with_suffix('')
            chat_file = next(extracted_folder.glob("*.txt"), None)
            
            if not chat_file:
                raise HTTPException(status_code=400, detail="No chat file found in ZIP")
                
            messages, count = await self._parse_and_process_messages(chat_file, extracted_folder)
            
            return messages, count
            
        finally:
            # Cleanup
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

    async def _parse_and_process_messages(
        self, 
        chat_file: Path, 
        extracted_folder: Path
    ) -> Tuple[List[ChatMessage], int]:
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

    async def _store_messages(self, messages: List[ChatMessage]):
        """Store messages in Firestore with deduplication."""
        batch = self.firebase.db.batch()
        messages_ref = self.firebase.db.collection('whatsapp_messages')
        
        for msg in messages:
            doc_id = self._generate_message_id(msg)
            
            if not self._message_exists(doc_id):  # No `await` here
                doc_ref = messages_ref.document(doc_id)
                batch.set(doc_ref, self._message_to_dict(msg))
                
        # Remove `await` here, as commit() is usually a synchronous call in Firestore
        batch.commit()

    async def _get_messages(self):
        """Retrieve messages from Firestore, sorted by timestamp."""
        messages_ref = self.firebase.db.collection('whatsapp_messages').order_by("timestamp")
        messages = messages_ref.stream()
        sorted_messages = [message.to_dict() for message in messages]
        print(sorted_messages)
        return sorted_messages


    def _message_exists(self, doc_id: str) -> bool:
        """Check if a message already exists in Firestore."""
        doc_ref = self.firebase.db.collection('whatsapp_messages').document(doc_id)
        doc_snapshot = doc_ref.get()  # Synchronously fetch the document
        return doc_snapshot.exists


    @staticmethod
    def _generate_message_id(msg: ChatMessage) -> str:
        """Generate a unique message ID based on message content and timestamp."""
        # Combine timestamp, sender, and message content for a unique identifier
        unique_str = f"{msg.timestamp}_{msg.sender}_{msg.message}"
        return hashlib.md5(unique_str.encode()).hexdigest()


    def _message_to_dict(self, msg: ChatMessage) -> Dict[str, str]:
        """Convert a ChatMessage instance to a dictionary for Firestore storage."""
        return {
            "timestamp": msg.timestamp.isoformat(),
            "sender": msg.sender,
            "message": msg.message,
            "media_urls": msg.media_urls,
        }

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
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

firebase_client = FirebaseClient()
chat_processor = ChatProcessor(firebase_client)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render home page with upload form."""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": "WhatsApp Chat Analyzer"
        }
    )

@app.post("/upload")
async def upload_chat(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
) -> RedirectResponse:
    """Handle chat file upload and processing."""
    try:
        messages, count = await chat_processor.process_chat_file(file)
        logger.info(f"Processed {count} messages successfully")
        
        return RedirectResponse(
            url=f"/chat?count={count}",
            status_code=303
        )
        
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to process chat file"
        )

@app.get("/chat")
async def display_chat(request: Request, count: int = 0):
    """Display processed chat messages."""
    messages = await chat_processor._get_messages()
    
    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "messages": messages,
            "count": count
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "error": exc.detail
        },
        status_code=exc.status_code
    )