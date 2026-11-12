import os
from fastapi import Depends, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from analyze import analyze
from auth import create_access_token, get_current_user, hash_password, verify_password
from database import (
    create_user,
    delete_user_analysis,
    get_user_analysis,
    get_user_by_email,
    init_db,
    list_user_analyses,
    save_analysis,
)
from extract import extract
from pdf_report import build_pdf_report

MAX_BYTES = 20 * 1024 * 1024

app = FastAPI(title="DocReview AI")

allowed_origins = os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in allowed_origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


class SignupRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    email: str = Field(..., min_length=5, max_length=120)
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: str
    password: str


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/auth/signup")
def signup(body: SignupRequest):
    if "@" not in body.email or "." not in body.email:
        raise HTTPException(400, "Please enter a valid email address.")
    if get_user_by_email(body.email):
        raise HTTPException(409, "An account with this email already exists.")
    user = create_user(body.name, body.email, hash_password(body.password))
    token = create_access_token(user["id"], user["email"])
    return {"token": token, "user": user}


@app.post("/api/auth/login")
def login(body: LoginRequest):
    user = get_user_by_email(body.email)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password.")
    token = create_access_token(user["id"], user["email"])
    safe_user = {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "created_at": user["created_at"],
    }
    return {"token": token, "user": safe_user}


@app.get("/api/auth/me")
def me(user: dict = Depends(get_current_user)):
    return {"user": user}


@app.post("/api/analyze")
def analyze_endpoint(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    name = file.filename or "document"
    if not name.lower().endswith((".pdf", ".docx")):
        raise HTTPException(400, "Only PDF and DOCX files are supported.")
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File is larger than 20 MB.")
    try:
        ex = extract(name, data)
    except RuntimeError as e:
        raise HTTPException(422, str(e))
    except Exception:
        raise HTTPException(422, "Could not read this file. It may be corrupted or password-protected.")
    if len(ex["text"].split()) < 30:
        raise HTTPException(
            422,
            "Almost no readable text found even after OCR. Please upload a clearer scan or document.",
        )
    report = analyze(name, ex)
    analysis_id = save_analysis(user["id"], report)
    report["id"] = analysis_id
    return report


@app.get("/api/history")
def get_history(user: dict = Depends(get_current_user)):
    return {"items": list_user_analyses(user["id"])}


@app.get("/api/history/{analysis_id}")
def get_history_item(analysis_id: int, user: dict = Depends(get_current_user)):
    report = get_user_analysis(user["id"], analysis_id)
    if not report:
        raise HTTPException(404, "Report not found.")
    return report


@app.delete("/api/history/{analysis_id}")
def delete_history_item(analysis_id: int, user: dict = Depends(get_current_user)):
    ok = delete_user_analysis(user["id"], analysis_id)
    if not ok:
        raise HTTPException(404, "Report not found.")
    return {"deleted": True}


@app.get("/api/history/{analysis_id}/pdf")
def download_history_pdf(analysis_id: int, user: dict = Depends(get_current_user)):
    report = get_user_analysis(user["id"], analysis_id)
    if not report:
        raise HTTPException(404, "Report not found.")
    pdf_bytes = build_pdf_report(report, user_name=user["name"])
    safe_name = report["filename"].rsplit(".", 1)[0] + "_review_report.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@app.post("/api/report/pdf")
def generate_ad_hoc_pdf(report: dict, user: dict = Depends(get_current_user)):
    pdf_bytes = build_pdf_report(report, user_name=user["name"])
    safe_name = str(report.get("filename", "document")).rsplit(".", 1)[0] + "_review_report.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )
