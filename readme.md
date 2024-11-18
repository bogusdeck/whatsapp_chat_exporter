# WhatsApp Chat Analyzer

<div align="center">
    <img src="https://github.com/user-attachments/assets/0c1a83e2-7631-4849-ab2c-277f75b39918" width="175"/>
</div>


A FastAPI-based application that uploads, parses, and analyzes exported WhatsApp chat files. This tool allows users to view chat messages, media files, and manage access through password-protected authentication.


<div align="center">
<a href="https://www.buymeacoffee.com/bogusdeck" target="_blank">
    <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me a Coffee" width="150" />
</a>
</div>

## Table of Contents
- [Features](#features)
- [Project Structure](#project-structure)
- [Setup and Installation](#setup-and-installation)
- [Environment Variables](#environment-variables)
- [Usage](#usage)
---

## Features

- **Upload and Parse Chats**: Upload a WhatsApp chat export in `.zip` format, parse messages, and display them in an interactive chat interface.
- **Media Upload to Firebase**: Automatically upload media attachments to Firebase Storage and display them in chat.
- **Password Protection**: Restrict access with a password stored securely in Firebase.
- **Pagination Support**: Load older and newer messages with pagination controls.
- **View Photos**: Dedicated photos page to view all media attachments in a gallery format.
- **Firebase Integration**: Store parsed messages and user data in Firebase Firestore and Firebase Storage.

## Project Structure

```
.
├── api
│   ├── index.py                # Main FastAPI application and endpoints
│   ├── utils.py                # Utility functions (e.g., parse_chat function)
├── templates                   # HTML templates for various pages
│   ├── index.html              # Chat upload page
│   ├── chat.html               # Chat display page
│   ├── photos.html             # Photos display page
│   ├── password_check.html     # Password entry page
│   ├── error.html              # Error display page
├── static                      # Static files (CSS, JS)
│   └── style.css               # Styles for the application
├── .env                        # Environment variables
├── requirements.txt            # Project dependencies
├── README.md                   # Project documentation

```

## Setup and Installation
Prerequisites

    Python 3.8+
    Firebase account with Firestore and Storage set up
    Firebase Admin SDK JSON key

### Installation

    Clone the Repository:

git clone https://github.com/yourusername/whatsapp-chat-analyzer.git
cd whatsapp-chat-analyzer

Install Dependencies:
```
pip install -r requirements.txt
```
Set Up Firebase:

    Place the Firebase Admin SDK JSON file in the root directory.
    Rename it if needed, and update the environment variable in .env.

Configure Environment Variables: Create a .env file in the root directory with the following variables (see Environment Variables section).

Run the Application:

    uvicorn api.index:app --reload

    Access the Application: Open http://127.0.0.1:8000 in your browser.

### Environment Variables

Configure the following variables in your .env file:
```
FIREBASE_SERVICE_ACCOUNT_KEY=<path-to-your-firebase-admin-sdk-json>
FIREBASE_STORAGE_BUCKET=<your-firebase-storage-bucket>
SECRET_KEY=<your-session-secret-key>
```
### Usage

- Password Protection:
   - Access the home page and enter the correct password to proceed. Password is stored securely in Firebase Firestore.
- Upload WhatsApp Chat:
   - Navigate to the chat upload page, select a .zip file containing your WhatsApp chat export, and submit. The application will parse the chat and upload media files to Firebase.
- View Chat Messages:
   - Messages are displayed in a paginated chat interface. Navigate between pages to see older or newer messages.
- View Photos:
   - Access the "Photos" page to view all media files associated with the chat.
- Logout:
   - Log out by clicking the "Logout" button to restrict access.
