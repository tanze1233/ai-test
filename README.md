# PDF Print Permission Remover

A small FastAPI web app that accepts a PDF upload from the browser and returns a copy with PDF print-permission restrictions removed.

> Only use this tool with PDFs you own or are explicitly authorized to modify.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>, choose a PDF, optionally enter the document open password, confirm authorization, and download the generated printable copy.

## API

`POST /unlock-print`

Multipart form fields:

- `file`: PDF file upload.
- `password`: optional PDF open password.
- `confirm_authorized`: must be `true`.

The response is an `application/pdf` attachment.
