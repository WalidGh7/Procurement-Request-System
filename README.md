# Smart Procurement System

A web application for creating and managing procurement requests with AI-powered document extraction and commodity classification.

## Features

- **Procurement Request Form** - Submit requests with vendor info, order lines, and auto-calculated totals
- **PDF Upload** - Upload vendor offers and auto-fill the form using AI
  - Supports both digital and scanned PDFs (OCR via Mistral Pixtral)
- **Smart Commodity Suggestions** - AI automatically suggests the correct commodity group
- **Request Management** - Track requests with status updates (Open → In Progress → Closed)


## Tech Stack

- **Backend:** FastAPI + LangChain + OpenAI + Mistral
- **Frontend:** Vanilla HTML/CSS/JavaScript
- **Database:** SQLite for persistent storage
- **AI:**
  - GPT-4o-mini for document extraction and classification
  - Pixtral-12B (Mistral) for OCR on scanned PDFs

## Quick Start

```bash
# Clone and enter directory
cd smart-procurement

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set your API keys
echo "OPENAI_API_KEY=your-openai-key-here" > .env
echo "MISTRAL_API_KEY=your-mistral-key-here" >> .env

# Run the server
python run.py
```

Open http://localhost:8000

## Project Structure

```
smart-procurement/
├── app/                 # Backend modules
│   ├── main.py          # FastAPI app
│   ├── models.py        # Data models
│   ├── routes/          # API endpoints
│   └── services/        # AI and database logic
│       ├── ai_service.py    # LangChain logic
│       └── database.py      # SQLite persistence
├── static/              # Frontend files
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── data/                # Data files
│   ├── *.pdf            # Sample vendor offers
│   └── procurement.db   # SQLite database (auto-created)
├── run.py               # Entry point
└── requirements.txt
```

## Usage

1. **New Request Tab**
   - Upload a PDF vendor offer (optional) - form auto-fills
   - Commodity group auto-suggests 
   - Submit when ready

2. **All Requests Tab**
   - View all submitted requests
   - Update status (Open → In Progress → Closed)
   - View status history
