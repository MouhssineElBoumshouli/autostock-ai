"""The data export's column headers (app/imports/fields.py: FIELD_LABELS) must be the kind of
headers our own import screen recognises by itself, in every language we write them in -- or a
shop's own export wouldn't come back in cleanly. See tests/test_export_round_trip.py for the
full, real round trip through the import screen.
"""

import pytest

from app.imports.fields import FIELD_LABELS, FIELDS
from app.imports.matching import suggest_field


@pytest.mark.parametrize("language", ["en", "fr", "ar"])
@pytest.mark.parametrize("kind", ["parts", "sales"])
def test_every_exported_header_is_recognised_without_help(language, kind):
    labels = FIELD_LABELS[language][kind]
    required = {field.key for field in FIELDS[kind] if field.required}
    assert required <= labels.keys(), f"{language}/{kind} is missing a header for a required field"
    for field_key, header in labels.items():
        assert suggest_field(header, kind) == field_key, f"{language}/{kind} header {header!r} -> {suggest_field(header, kind)!r}, expected {field_key!r}"
