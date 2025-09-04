"""
Upload service for handling file uploads and metadata storage
"""
import os
import uuid
from datetime import datetime
import aiofiles
from fastapi import UploadFile
from sqlalchemy.orm import Session
from src.models.upload import DataUpload
from src.utils.file_validation import sanitize_filename


async def save_uploaded_file(file: UploadFile, upload_dir: str) -> str:
    """Save uploaded file to directory with unique filename"""
    os.makedirs(upload_dir, exist_ok=True)
    
    unique_filename = generate_unique_filename(file.filename)
    file_path = os.path.join(upload_dir, unique_filename)
    
    content = await file.read()
    
    # Open file and write content
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(content)
    
    return file_path


async def store_file_metadata(file_info: dict, db: Session) -> DataUpload:
    """Create DataUpload database record"""
    upload = DataUpload(
        id=str(uuid.uuid4()),
        filename=file_info["filename"],
        file_size=file_info["file_size"],
        file_type=file_info["file_type"],
        status=file_info.get("status", "pending"),
        created_at=datetime.now()
    )
    
    db.add(upload)
    db.commit()
    
    return upload


def generate_unique_filename(original_filename: str) -> str:
    """Generate unique filename with UUID prefix"""
    # Extract extension first
    if '.' in original_filename:
        name, ext = os.path.splitext(original_filename)
        sanitized_name = sanitize_filename(name)
        sanitized = f"{sanitized_name}{ext}"
    else:
        sanitized = sanitize_filename(original_filename)
    
    uuid_prefix = str(uuid.uuid4())[:8]
    return f"{uuid_prefix}_{sanitized}"


async def get_upload_status(upload_id: str, db: Session) -> dict:
    """Get upload status from database"""
    upload = db.query(DataUpload).filter(DataUpload.id == upload_id).first()
    
    if not upload:
        return None
    
    return {
        "id": upload.id,
        "filename": upload.filename,
        "status": upload.status,
        "created_at": upload.created_at
    }