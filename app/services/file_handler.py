import os
import shutil
import uuid
from fastapi import UploadFile

UPLOAD_DIR = "uploads"

def save_upload_file(upload_file: UploadFile) -> str:
    """
    Saves an uploaded file to the local disk and returns the file path.
    """
    # 1. Ensure the uploads directory exists
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # 2. Generate a universally unique filename
    unique_filename = f"{uuid.uuid4()}_{upload_file.filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    # 3. Open a new empty file in 'write-binary' (wb) mode and pour the data in
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)

    return file_path