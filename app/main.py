from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path

import pikepdf
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
PDF_MEDIA_TYPE = "application/pdf"
SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")

app = FastAPI(
    title="PDF Print Permission Remover",
    description=(
        "Upload a PDF you own or are authorized to modify and download a copy "
        "with print-permission restrictions removed."
    ),
    version="1.0.0",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@dataclass(frozen=True)
class ProcessedPdf:
    filename: str
    data: bytes


def sanitize_filename(filename: str) -> str:
    """Return a safe download filename while keeping a .pdf extension."""
    original_name = Path(filename or "document.pdf").name
    stem = Path(original_name).stem or "document"
    safe_stem = SAFE_FILENAME_RE.sub("_", stem).strip("._") or "document"
    return f"{safe_stem}-print-enabled.pdf"


def remove_print_protection(pdf_bytes: bytes, password: str | None = None) -> bytes:
    """
    Create an unencrypted PDF copy, which clears PDF permission flags such as
    print restrictions. This is intended only for documents the caller owns or
    is explicitly authorized to modify.
    """
    password = password or ""
    try:
        with pikepdf.open(io.BytesIO(pdf_bytes), password=password) as pdf:
            output = io.BytesIO()
            pdf.save(output, encryption=False)
            return output.getvalue()
    except pikepdf.PasswordError as exc:
        raise ValueError("该 PDF 需要正确的打开密码后才能处理。") from exc
    except pikepdf.PdfError as exc:
        raise ValueError("无法读取该文件，请确认它是有效的 PDF。") from exc


async def read_upload(upload: UploadFile) -> bytes:
    if upload.content_type and upload.content_type not in {
        PDF_MEDIA_TYPE,
        "application/x-pdf",
        "application/octet-stream",
    }:
        raise HTTPException(status_code=400, detail="请上传 PDF 文件。")

    contents = await upload.read()
    if not contents:
        raise HTTPException(status_code=400, detail="上传的文件为空。")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="文件超过 50 MB 限制。")
    if not contents.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="文件头不是有效的 PDF。")
    return contents


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.post("/unlock-print")
async def unlock_print(
    file: UploadFile = File(...),
    password: str | None = Form(default=None),
    confirm_authorized: bool = Form(default=False),
) -> StreamingResponse:
    if not confirm_authorized:
        raise HTTPException(status_code=400, detail="请先确认你有权修改该 PDF。")

    pdf_bytes = await read_upload(file)
    try:
        unlocked = remove_print_protection(pdf_bytes, password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    processed = ProcessedPdf(filename=sanitize_filename(file.filename), data=unlocked)
    headers = {"Content-Disposition": f'attachment; filename="{processed.filename}"'}
    return StreamingResponse(
        io.BytesIO(processed.data),
        media_type=PDF_MEDIA_TYPE,
        headers=headers,
    )
