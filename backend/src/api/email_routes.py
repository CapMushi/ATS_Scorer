from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import tempfile
import uuid

from ..utils.imap_client import IMAPClient

router = APIRouter(prefix="/emails", tags=["Emails"])

# Dictionary to hold temp file mappings for downloading
# Key: string (file_id), Value: str (absolute filepath)
temp_file_store = {}

class EmailScanRequest(BaseModel):
    email_address: str
    app_password: str
    since_date: str
    subject_filter: str = ""

class ScannedFile(BaseModel):
    file_id: str
    filename: str

class EmailScanResponse(BaseModel):
    total_found: int
    files: List[ScannedFile]

@router.post("/scan", response_model=EmailScanResponse)
async def scan_emails_for_cvs(req: EmailScanRequest):
    client = None
    try:
        client = IMAPClient(req.email_address, req.app_password)
        cvs = client.fetch_cvs(req.since_date, req.subject_filter)
        
        result_files = []
        for filepath, filename, message_id in cvs:
            file_id = str(uuid.uuid4())
            temp_file_store[file_id] = filepath
            result_files.append(ScannedFile(file_id=file_id, filename=filename))
            
        return {"total_found": len(result_files), "files": result_files}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if client:
            client.close()

@router.get("/download/{file_id}")
async def download_email_cv(file_id: str):
    if file_id not in temp_file_store:
        raise HTTPException(status_code=404, detail="File not found or expired")
    
    filepath = temp_file_store[file_id]
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File no longer exists on server")
        
    # Extract original filename from the stored path if needed, 
    # but the frontend will rename it from the scan response anyway.
    return FileResponse(filepath)
