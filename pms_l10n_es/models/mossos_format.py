# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
import re
import unicodedata

from odoo import _
from odoo.exceptions import ValidationError

TRAVELLER_LENGTHS = (
    1, 11, 14, 1, 8, 30, 30, 30, 1, 8, 21, 8, 4, 8, 4, 8,
    1, 20, 3, 3, 1, 5, 20, 2, 100, 9, 100, 2, 6, 100, 3, 20,
)
HEADER_LENGTHS = (1, 10, 40, 8, 4, 5, 3)


def v24_record(values, lengths):
    """Normalize Latin text without dropping or silently shortening data."""
    if len(values) != len(lengths):
        raise ValidationError(_("Unexpected number of Mossos record fields."))
    normalized = []
    for position, (value, limit) in enumerate(zip(values, lengths), 1):
        raw = str(value) if value is not False and value is not None else ""
        for character in raw:
            category = unicodedata.category(character)
            if character == "|" or category in ("Cc", "Cf", "Cs", "Zl", "Zp"):
                raise ValidationError(_("Field %s contains a separator or control character.", position))
            non_latin_letter = (
                category.startswith("L")
                and "LATIN" not in unicodedata.name(character, "")
                and character not in "ªº"
            )
            if non_latin_letter or (category == "So" and ord(character) > 255):
                raise ValidationError(_("Field %s must use the Western alphabet.", position))
        text = unicodedata.normalize("NFC", raw.strip()).upper()
        if len(text) > limit:
            raise ValidationError(_("Field %(field)s exceeds %(length)s characters.", field=position, length=limit))
        normalized.append(text)
    return "|".join(normalized)


def valid_spanish_document(number, kind):
    number = (number or "").upper()
    pattern = r"[0-9]{8}[A-Z]" if kind == "D" else r"[XYZ][0-9]{7}[A-Z]"
    if not re.fullmatch(pattern, number):
        return False
    digits = number[:-1]
    if kind == "N":
        digits = str("XYZ".index(digits[0])) + digits[1:]
    return number[-1] == "TRWAGMYFPDXBNJZSQVHLCKE"[int(digits) % 23]
