# DocReview AI — Full-Stack Document Review System

## Features Included
1. **Authentication & Per-User History**: Signup/Login with JWT tokens and SQLite persistence (`database.py` + `auth.py`). Each user sees and manages only their own past reviews.
2. **Scanned PDF OCR**: Automatically detects image-only / scanned PDFs in `extract.py` and runs Tesseract OCR (`pytesseract` + PyMuPDF rendering).
3. **Capitalization Checker**: Detects lowercase sentence starts, standalone lowercase pronoun `i`, and excessive ALL-CAPS in headings/body.
4. **Grammar & Style Checker**: Flags repeated consecutive words, `a/an` mismatches, modal errors (`could of`), common misspellings, spacing errors, countable `less`, and informal contractions.
5. **Citation Checker**: Detects Author-Year (`(Smith, 2023)`) and Numeric (`[1]`) inline citations, checks consistency, and cross-verifies against the `References` section.
6. **Downloadable PDF Report**: Generates a formatted PDF audit report via ReportLab (`/api/history/{id}/pdf` and `/api/report/pdf`).
7. **Deployment Ready**: Includes `Dockerfile` for both backend (with `tesseract-ocr` pre-installed) and frontend (Nginx reverse proxy), `docker-compose.yml`, `render.yaml`, and `.env.example`.

---

## Local Development

### 1. Backend (FastAPI)
*(Optional for scanned PDFs locally: install Tesseract OCR on your OS — e.g., `sudo apt install tesseract-ocr` on Ubuntu/Debian or `brew install tesseract` on macOS).*
```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 2. Frontend (React + Vite)
```bash
cd docreview
npm install
npm run dev
```
Open `http://localhost:5173`.

---

## Production Deployment (Docker Compose)
```bash
cp .env.example .env
# Edit JWT_SECRET in .env
docker compose up --build -d
```
App runs on `http://localhost` (port 80) with `/api` automatically proxied to FastAPI.
