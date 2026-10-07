import re
from datetime import date

from wtforms.validators import ValidationError

PHONE_REGEX = re.compile(r"^\+?[0-9]{7,15}$")


def valid_phone_number(form, field):
    if not field.data:
        return
    cleaned = re.sub(r"[\s\-()]", "", field.data)
    if not PHONE_REGEX.match(cleaned):
        raise ValidationError("Enter a valid phone number (7-15 digits, optional +country code).")
    field.data = cleaned


def not_in_past(form, field):
    if field.data and field.data < date.today():
        raise ValidationError("Date cannot be in the past.")


def strong_password(form, field):
    value = field.data or ""
    if len(value) < 8:
        raise ValidationError("Password must be at least 8 characters long.")
    if not re.search(r"[A-Z]", value):
        raise ValidationError("Password must contain at least one uppercase letter.")
    if not re.search(r"[0-9]", value):
        raise ValidationError("Password must contain at least one digit.")


def max_file_size_mb(max_mb):
    def _validator(form, field):
        file_storage = field.data
        if not file_storage or not hasattr(file_storage, "stream") or not getattr(file_storage, "filename", None):
            return
        file_storage.stream.seek(0, 2)
        size_bytes = file_storage.stream.tell()
        file_storage.stream.seek(0)
        if size_bytes > max_mb * 1024 * 1024:
            raise ValidationError(f"File must be smaller than {max_mb} MB.")

    return _validator