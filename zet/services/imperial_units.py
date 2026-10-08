"""Parse, format, and convert the feet/inches used in scene authoring."""

from __future__ import annotations

from fractions import Fraction
import re


_NUMBER = r"(?:\d+(?:\.\d+)?|\d+\s+\d+\s*/\s*\d+|\d+\s*/\s*\d+)"
_FEET_INCHES = re.compile(
    rf"^\s*(?P<feet>-?\d+)\s*(?:ft|feet|foot|')\s*"
    rf"(?P<inches>{_NUMBER})?\s*(?:in|inches|inch|\")?\s*$",
    re.IGNORECASE,
)
_INCHES_ONLY = re.compile(rf"^\s*(?P<inches>{_NUMBER})\s*(?:in|inches|inch|\")\s*$", re.IGNORECASE)


def _number(value: str) -> float:
    if "/" in value:
        whole, separator, fraction = re.sub(r"\s+", " ", value).strip().partition(" ")
        if separator and "/" in fraction:
            return int(whole) + float(Fraction(fraction))
        return float(Fraction(re.sub(r"\s+", "", value)))
    return float(value)


def parse_feet_inches(value: str) -> float:
    """Parse a feet/inches string and return meters. Negative values are supported."""
    text = str(value or "").strip()
    match = _FEET_INCHES.fullmatch(text)
    if match:
        feet = int(match.group("feet"))
        try:
            inches = _number(match.group("inches")) if match.group("inches") else 0.0
        except (ValueError, ZeroDivisionError) as exc:
            raise ValueError(f"Invalid feet/inches value: {value!r}") from exc
        sign = -1 if feet < 0 or re.match(r"^\s*-", text) else 1
        total_inches = feet * 12 + sign * inches
    else:
        match = _INCHES_ONLY.fullmatch(text)
        if not match:
            raise ValueError(f"Invalid feet/inches value: {value!r}")
        try:
            total_inches = _number(match.group("inches"))
        except (ValueError, ZeroDivisionError) as exc:
            raise ValueError(f"Invalid feet/inches value: {value!r}") from exc
    return total_inches * 0.0254


def meters_to_feet_inches(meters: float, *, denominator: int = 16) -> tuple[int, Fraction]:
    """Return signed whole feet and an inches fraction rounded to denominator."""
    total_inches = Fraction(str(float(meters) / 0.0254))
    sign = -1 if total_inches < 0 else 1
    total_inches = abs(total_inches)
    feet = int(total_inches // 12)
    inches = total_inches - feet * 12
    inches = round(float(inches) * denominator) / denominator
    if inches >= 12:
        feet += 1
        inches = 0
    return sign * feet, Fraction(inches).limit_denominator(denominator)


def format_feet_inches(meters: float, *, denominator: int = 16) -> str:
    feet, inches = meters_to_feet_inches(meters, denominator=denominator)
    sign = "-" if meters < 0 else ""
    whole_inches = inches.numerator // inches.denominator
    fractional_inches = inches - whole_inches
    if fractional_inches:
        inch_text = f"{whole_inches} {fractional_inches}" if whole_inches else str(fractional_inches)
    else:
        inch_text = str(whole_inches)
    return f"{sign}{abs(feet)} ft {inch_text} in"
