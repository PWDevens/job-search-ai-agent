"""
Input validation and security constraints.

Validates:
  - Form field lengths and content
  - File sizes and types
  - Role/geo descriptions
  - Rate limiting on search endpoint
"""
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# Constants
MAX_ROLE_LENGTH = 500
MAX_GEO_LENGTH = 100
MAX_CONTEXT_LENGTH = 1000
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16 MB
MAX_SEARCHES_PER_MINUTE = 10


class ValidationError(ValueError):
    """Raised when input validation fails."""
    pass


def validate_role_description(role: str) -> str:
    """
    Validate role description input.

    Returns:
        Validated and stripped role description

    Raises:
        ValidationError: If invalid
    """
    if not role:
        raise ValidationError("Role description is required")

    role = role.strip()

    if len(role) < 3:
        raise ValidationError("Role description must be at least 3 characters")

    if len(role) > MAX_ROLE_LENGTH:
        raise ValidationError(
            f"Role description must be under {MAX_ROLE_LENGTH} characters "
            f"(got {len(role)})"
        )

    # Check for SQL injection attempts
    dangerous_patterns = ["'", '"', "--", "/*", "*/", "xp_", "sp_", ";"]
    if any(pattern in role.lower() for pattern in dangerous_patterns):
        logger.warning("Suspicious input detected in role description")
        raise ValidationError("Role description contains invalid characters")

    return role


def validate_geo_preference(geo: str) -> str:
    """
    Validate geographic preference input.

    Returns:
        Validated and stripped geo preference (or empty string)

    Raises:
        ValidationError: If invalid
    """
    if not geo or not geo.strip():
        return ""

    geo = geo.strip()

    if len(geo) > MAX_GEO_LENGTH:
        raise ValidationError(
            f"Location must be under {MAX_GEO_LENGTH} characters "
            f"(got {len(geo)})"
        )

    # Basic validation: only alphanumeric, spaces, commas, dashes
    import re
    if not re.match(r"^[a-zA-Z0-9\s,\-]*$", geo):
        raise ValidationError(
            "Location contains invalid characters. Use only letters, numbers, "
            "spaces, commas, and dashes."
        )

    return geo


def validate_extra_context(context: str) -> str:
    """
    Validate extra context field.

    Returns:
        Validated and stripped context (or empty string)

    Raises:
        ValidationError: If invalid
    """
    if not context or not context.strip():
        return ""

    context = context.strip()

    if len(context) > MAX_CONTEXT_LENGTH:
        raise ValidationError(
            f"Extra context must be under {MAX_CONTEXT_LENGTH} characters "
            f"(got {len(context)})"
        )

    return context


def validate_file_upload(filename: str, file_size: int) -> Tuple[str, int]:
    """
    Validate uploaded file size and name.

    Returns:
        Tuple of (filename, file_size) if valid

    Raises:
        ValidationError: If invalid
    """
    if not filename or not filename.strip():
        raise ValidationError("Filename is required")

    if file_size <= 0:
        raise ValidationError("File is empty")

    if file_size > MAX_FILE_SIZE:
        raise ValidationError(
            f"File too large ({file_size/1024/1024:.1f}MB). "
            f"Maximum is {MAX_FILE_SIZE/1024/1024:.1f}MB."
        )

    # Check for path traversal attempts
    if ".." in filename or "/" in filename or "\\" in filename:
        logger.warning("Suspicious filename detected: %s", filename)
        raise ValidationError("Invalid filename")

    return filename, file_size


def validate_search_input(
    role_description: str,
    geo_preference: str = None,
    extra_context: str = None,
) -> Tuple[str, str, str]:
    """
    Validate complete search input.

    Returns:
        Tuple of (role, geo, context) all validated

    Raises:
        ValidationError: If any field invalid
    """
    role = validate_role_description(role_description)
    geo = validate_geo_preference(geo_preference or "")
    context = validate_extra_context(extra_context or "")

    return role, geo, context
