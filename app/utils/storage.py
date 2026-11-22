"""
Smriti Shuddhi - Cloud & Local Hybrid Object Storage
====================================================
Handles binary document attachments (.pdf, .docx, images, logs)
with direct Supabase Storage bucket integration and local fallback.
"""

import os
import io
import mimetypes
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import urllib.request
import urllib.error

import config

logger = logging.getLogger("StorageService")

LOCAL_UPLOAD_DIR = Path("static/uploads")
LOCAL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def get_content_type(filename: str) -> str:
    ctype, _ = mimetypes.guess_type(filename)
    return ctype or "application/octet-stream"


def upload_to_supabase_storage(filename: str, file_bytes: bytes, content_type: Optional[str] = None) -> Optional[str]:
    """Uploads file to Supabase Storage bucket via REST API.
    Returns public asset URL if successful, else None.
    """
    supabase_url = (config.SUPABASE_URL or "").strip().rstrip('/')
    supabase_key = (config.SUPABASE_KEY or "").strip()
    bucket = config.SUPABASE_STORAGE_BUCKET or "smriti-shuddhi-storage"

    if not supabase_url or not supabase_key:
        return None

    ctype = content_type or get_content_type(filename)
    url = f"{supabase_url}/storage/v1/object/{bucket}/{filename}"
    headers = {
        "Authorization": f"Bearer {supabase_key}",
        "apikey": supabase_key,
        "Content-Type": ctype,
        "x-upsert": "true"
    }

    try:
        req = urllib.request.Request(url, data=file_bytes, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            if resp.status in [200, 201]:
                public_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{filename}"
                logger.info("Uploaded %s to Supabase bucket '%s' successfully.", filename, bucket)
                return public_url
    except Exception as e:
        logger.info("Supabase storage upload notice: %s. Using local asset storage.", e)

    return None


def upload_to_local_storage(filename: str, file_bytes: bytes) -> str:
    """Saves file to static/uploads/ directory and returns local asset URL."""
    clean_name = os.path.basename(filename).replace(" ", "_")
    dest_path = LOCAL_UPLOAD_DIR / clean_name
    dest_path.write_bytes(file_bytes)
    return f"/static/uploads/{clean_name}"


def store_document_attachment(filename: str, file_bytes: bytes, content_type: Optional[str] = None) -> Dict[str, Any]:
    """Hybrid document storage gateway:
    1. Tries Supabase Object Storage (bucket: smriti-shuddhi-storage)
    2. Falls back cleanly to local disk (/static/uploads/...)
    """
    # Try Supabase Storage first
    public_url = upload_to_supabase_storage(filename, file_bytes, content_type)
    if public_url:
        return {
            "success": True,
            "url": public_url,
            "storage_provider": "supabase_storage",
            "bucket": config.SUPABASE_STORAGE_BUCKET,
            "filename": filename,
            "size_bytes": len(file_bytes)
        }

    # Fallback to local storage
    local_url = upload_to_local_storage(filename, file_bytes)
    return {
        "success": True,
        "url": local_url,
        "storage_provider": "local_filesystem",
        "bucket": "local",
        "filename": filename,
        "size_bytes": len(file_bytes)
    }
