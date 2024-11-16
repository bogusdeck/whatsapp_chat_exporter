```
.
├── /api/
│   └── index.py                 # FastAPI routes and logic (main logic here)
   └── secret.py                # checkpassword and make password here
    └── utils.py                 # chat extraction logic 
├── /src/
│   ├── __main__.py               # Entry point for local runs (optional)
│   └── index.py                  # Additional logic, if needed
├── /templates/
│   └── chat.html                 # Jinja template for chat UI
├── /static/                      # Folder for Tailwind CSS (optional)
│   └── style.css
├── /chat_uploads/                # Store uploaded chat zips
├── utils.py                      # Helper functions (ZIP extraction, parsing)
├── .gitignore
├── requirements.txt              # Dependencies
├── vercel.json                   # Vercel config
└── main.py                       # Main FastAPI entry point (for Vercel)

```

uvicorn index:app --reload
start command
```
uvicorn index:app --reload
```