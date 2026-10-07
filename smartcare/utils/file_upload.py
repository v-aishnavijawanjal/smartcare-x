import os
import uuid

from flask import current_app
from werkzeug.utils import secure_filename


def _allowed(filename, allowed_extensions):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def _unique_filename(original_filename):
    ext = secure_filename(original_filename).rsplit(".", 1)[-1].lower()
    return f"{uuid.uuid4().hex}.{ext}"


def save_profile_photo(file_storage):
    """Save a profile photo and return its filename."""
    if not file_storage or file_storage.filename == "":
        return None

    allowed = current_app.config["ALLOWED_IMAGE_EXTENSIONS"]
    if not _allowed(file_storage.filename, allowed):
        raise ValueError("Unsupported image format. Allowed: " + ", ".join(sorted(allowed)))

    filename = _unique_filename(file_storage.filename)
    subdir = current_app.config["PROFILE_PHOTO_SUBDIR"]
    dest_path = os.path.join(current_app.config["UPLOAD_FOLDER"], subdir, filename)
    file_storage.save(dest_path)
    return filename


def save_medical_report(file_storage):
    """Save a medical report and return its relative path."""
    if not file_storage or file_storage.filename == "":
        raise ValueError("No file was provided.")

    allowed = current_app.config["ALLOWED_DOCUMENT_EXTENSIONS"]
    if not _allowed(file_storage.filename, allowed):
        raise ValueError("Unsupported file format. Allowed: " + ", ".join(sorted(allowed)))

    filename = _unique_filename(file_storage.filename)
    subdir = current_app.config["LAB_REPORT_SUBDIR"]
    dest_path = os.path.join(current_app.config["UPLOAD_FOLDER"], subdir, filename)
    file_storage.save(dest_path)
    return f"{subdir}/{filename}"


def delete_uploaded_file(relative_path):
    """Delete an uploaded file if it exists."""
    full_path = os.path.join(current_app.config["UPLOAD_FOLDER"], relative_path)
    try:
        os.remove(full_path)
    except OSError:
        pass