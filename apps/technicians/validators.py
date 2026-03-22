"""
Dynamic form field validators.

``validate_answers_against_schema`` validates submitted answers against the
form's field definitions. Empty dict means valid.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any
from urllib.parse import urlparse

from apps.technicians.models import FormFieldType


def validate_answers_against_schema(
    fields: list[dict],
    answers: dict[str, Any],
    *,
    partial: bool = False,
) -> dict[str, list[str]]:
    """
    Validate ``answers`` against ``fields`` (list of field-schema dicts).

    partial: if True, missing values for required fields are not flagged.
    """
    errors: dict[str, list[str]] = {}
    field_keys: set[str] = set()

    for field_def in fields:
        fk = field_def["field_key"]
        field_keys.add(fk)
        field_errors = _validate_single_field(
            field_def, answers.get(fk), partial=partial
        )
        if field_errors:
            errors[fk] = field_errors

    unknown = set(answers.keys()) - field_keys
    for key in sorted(unknown):
        errors[key] = [f"Unknown field '{key}'."]

    return errors


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    return False


def _validate_single_field(
    field_def: dict,
    value: Any,
    *,
    partial: bool = False,
) -> list[str]:
    errors: list[str] = []
    field_type = field_def.get("field_type", "text")
    required = field_def.get("required", False)
    validations = field_def.get("validations") or {}

    if _is_empty(value):
        if required and not partial:
            errors.append("This field is required.")
        return errors

    type_validator = _TYPE_VALIDATORS.get(field_type, _validate_text)
    errors.extend(type_validator(value, field_def, validations))
    return errors


def _validate_text(value: Any, field_def: dict, validations: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, str):
        return ["Expected a text value."]

    v = value.strip()
    min_len = validations.get("min_length")
    max_len = validations.get("max_length")
    if min_len is not None and len(v) < int(min_len):
        errors.append(f"Must be at least {min_len} characters.")
    if max_len is not None and len(v) > int(max_len):
        errors.append(f"Must be at most {max_len} characters.")

    pattern = validations.get("pattern")
    if pattern:
        try:
            if not re.fullmatch(pattern, v):
                msg = validations.get(
                    "pattern_message", "Does not match required pattern."
                )
                errors.append(msg)
        except re.error:
            pass

    return errors


def _validate_textarea(value: Any, field_def: dict, validations: dict) -> list[str]:
    return _validate_text(value, field_def, validations)


def _validate_email(value: Any, field_def: dict, validations: dict) -> list[str]:
    if not isinstance(value, str):
        return ["Expected a text value."]
    v = value.strip()
    if "@" not in v or "." not in v.split("@")[-1]:
        return ["Enter a valid email address."]
    max_len = validations.get("max_length", 254)
    if len(v) > int(max_len):
        return [f"Must be at most {max_len} characters."]
    return []


def _validate_phone(value: Any, field_def: dict, validations: dict) -> list[str]:
    if not isinstance(value, str):
        return ["Expected a text value."]
    v = value.strip()
    cleaned = re.sub(r"[\s\-\(\)\.\+]", "", v)
    if not cleaned.isdigit():
        return ["Enter a valid phone number."]
    min_len = validations.get("min_length", 7)
    max_len = validations.get("max_length", 20)
    if len(cleaned) < int(min_len):
        return [f"Phone number must have at least {min_len} digits."]
    if len(cleaned) > int(max_len):
        return [f"Phone number must have at most {max_len} digits."]
    return []


def _validate_number(value: Any, field_def: dict, validations: dict) -> list[str]:
    errors: list[str] = []
    if isinstance(value, str):
        try:
            value = float(value)
        except (ValueError, TypeError):
            return ["Enter a valid number."]
    if not isinstance(value, (int, float)):
        return ["Enter a valid number."]

    min_val = validations.get("min_value")
    max_val = validations.get("max_value")
    if min_val is not None and value < float(min_val):
        errors.append(f"Must be at least {min_val}.")
    if max_val is not None and value > float(max_val):
        errors.append(f"Must be at most {max_val}.")
    return errors


def _validate_checkbox(value: Any, field_def: dict, validations: dict) -> list[str]:
    if not isinstance(value, bool):
        return ["Expected true or false."]
    if field_def.get("required") and value is False:
        return ["This field must be checked."]
    return []


def _get_option_values(field_def: dict) -> set[str]:
    options = field_def.get("options") or []
    values: set[str] = set()
    for opt in options:
        if isinstance(opt, dict):
            values.add(str(opt.get("value", "")))
        elif isinstance(opt, str):
            values.add(opt)
    return values


def _validate_select(value: Any, field_def: dict, validations: dict) -> list[str]:
    if not isinstance(value, str):
        return ["Expected a single selected value."]
    allowed = _get_option_values(field_def)
    if allowed and value not in allowed:
        return [f"'{value}' is not a valid option."]
    return []


def _validate_multi_select(value: Any, field_def: dict, validations: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, list):
        return ["Expected a list of selected values."]

    allowed = _get_option_values(field_def)
    for item in value:
        if not isinstance(item, str):
            errors.append(
                f"Each selection must be a string; got {type(item).__name__}."
            )
            break
        if allowed and item not in allowed:
            errors.append(f"'{item}' is not a valid option.")

    min_sel = validations.get("min_selections")
    max_sel = validations.get("max_selections")
    if min_sel is not None and len(value) < int(min_sel):
        errors.append(f"Select at least {min_sel} option(s).")
    if max_sel is not None and len(value) > int(max_sel):
        errors.append(f"Select at most {max_sel} option(s).")

    return errors


def _validate_radio(value: Any, field_def: dict, validations: dict) -> list[str]:
    return _validate_select(value, field_def, validations)


def _validate_date(value: Any, field_def: dict, validations: dict) -> list[str]:
    if not isinstance(value, str):
        return ["Expected a date string (YYYY-MM-DD)."]
    try:
        date.fromisoformat(value)
    except (ValueError, TypeError):
        return ["Enter a valid date in YYYY-MM-DD format."]
    return []


def _validate_url(value: Any, field_def: dict, validations: dict) -> list[str]:
    if not isinstance(value, str):
        return ["Expected a URL string."]
    v = value.strip()
    parsed = urlparse(v)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return ["Enter a valid URL starting with http:// or https://."]
    max_len = validations.get("max_length", 2048)
    if len(v) > int(max_len):
        return [f"URL must be at most {max_len} characters."]
    return []


def _validate_file_upload(value: Any, field_def: dict, validations: dict) -> list[str]:
    if not isinstance(value, (str, dict)):
        return ["Expected a file reference."]
    if isinstance(value, dict):
        filename = value.get("filename", "")
        if not filename:
            return ["File reference must include a filename."]
    else:
        filename = value

    allowed_ext = validations.get("allowed_extensions")
    if allowed_ext and isinstance(allowed_ext, list):
        ext = ""
        if "." in filename:
            ext = "." + filename.rsplit(".", 1)[-1].lower()
        lowered = [e.lower() for e in allowed_ext]
        if ext not in lowered:
            return [
                f"File type '{ext}' is not allowed. Accepted: {', '.join(allowed_ext)}."
            ]

    return []


_TYPE_VALIDATORS = {
    FormFieldType.TEXT: _validate_text,
    FormFieldType.TEXTAREA: _validate_textarea,
    FormFieldType.EMAIL: _validate_email,
    FormFieldType.PHONE: _validate_phone,
    FormFieldType.NUMBER: _validate_number,
    FormFieldType.CHECKBOX: _validate_checkbox,
    FormFieldType.SELECT: _validate_select,
    FormFieldType.MULTI_SELECT: _validate_multi_select,
    FormFieldType.RADIO: _validate_radio,
    FormFieldType.DATE: _validate_date,
    FormFieldType.URL: _validate_url,
    FormFieldType.FILE_UPLOAD: _validate_file_upload,
    "text": _validate_text,
    "textarea": _validate_textarea,
    "email": _validate_email,
    "phone": _validate_phone,
    "number": _validate_number,
    "checkbox": _validate_checkbox,
    "select": _validate_select,
    "multi_select": _validate_multi_select,
    "radio": _validate_radio,
    "date": _validate_date,
    "url": _validate_url,
    "file_upload": _validate_file_upload,
}
