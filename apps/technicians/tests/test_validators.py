"""
Tests for the dynamic form field validation engine.
"""

from django.test import SimpleTestCase

from apps.technicians.validators import validate_answers_against_schema


def _field(field_key="test_field", field_type="text", required=False, **kwargs):
    return {
        "field_key": field_key,
        "field_type": field_type,
        "required": required,
        "options": kwargs.pop("options", []),
        "validations": kwargs.pop("validations", {}),
        **kwargs,
    }


class TestRequiredFields(SimpleTestCase):
    def test_required_field_missing_value(self):
        fields = [_field("name", "text", required=True)]
        errors = validate_answers_against_schema(fields, {})
        self.assertIn("name", errors)
        self.assertTrue(any("required" in e.lower() for e in errors["name"]))

    def test_required_field_empty_string(self):
        fields = [_field("name", "text", required=True)]
        errors = validate_answers_against_schema(fields, {"name": ""})
        self.assertIn("name", errors)

    def test_required_field_whitespace_only(self):
        fields = [_field("name", "text", required=True)]
        errors = validate_answers_against_schema(fields, {"name": "   "})
        self.assertIn("name", errors)

    def test_required_field_with_value(self):
        fields = [_field("name", "text", required=True)]
        errors = validate_answers_against_schema(fields, {"name": "Alice"})
        self.assertEqual(errors, {})

    def test_optional_field_missing(self):
        fields = [_field("notes", "text", required=False)]
        errors = validate_answers_against_schema(fields, {})
        self.assertEqual(errors, {})

    def test_partial_mode_skips_required(self):
        fields = [_field("name", "text", required=True)]
        errors = validate_answers_against_schema(fields, {}, partial=True)
        self.assertEqual(errors, {})


class TestTextValidation(SimpleTestCase):
    def test_valid_text(self):
        fields = [_field("name", "text")]
        self.assertEqual(
            validate_answers_against_schema(fields, {"name": "Hello"}), {}
        )

    def test_min_length(self):
        fields = [_field("name", "text", validations={"min_length": 5})]
        errors = validate_answers_against_schema(fields, {"name": "Hi"})
        self.assertIn("name", errors)

    def test_max_length(self):
        fields = [_field("name", "text", validations={"max_length": 3})]
        errors = validate_answers_against_schema(fields, {"name": "Hello"})
        self.assertIn("name", errors)

    def test_pattern_match(self):
        fields = [
            _field(
                "zip",
                "text",
                validations={
                    "pattern": r"\d{5}",
                    "pattern_message": "Enter 5 digits.",
                },
            )
        ]
        self.assertEqual(validate_answers_against_schema(fields, {"zip": "12345"}), {})
        errors = validate_answers_against_schema(fields, {"zip": "abc"})
        self.assertIn("zip", errors)
        self.assertIn("5 digits", errors["zip"][0])

    def test_non_string_rejected(self):
        fields = [_field("name", "text")]
        errors = validate_answers_against_schema(fields, {"name": 123})
        self.assertIn("name", errors)


class TestTextareaValidation(SimpleTestCase):
    def test_valid(self):
        fields = [_field("bio", "textarea")]
        self.assertEqual(
            validate_answers_against_schema(fields, {"bio": "Long text here"}), {}
        )

    def test_min_length(self):
        fields = [_field("bio", "textarea", validations={"min_length": 10})]
        errors = validate_answers_against_schema(fields, {"bio": "Short"})
        self.assertIn("bio", errors)


class TestEmailValidation(SimpleTestCase):
    def test_valid(self):
        fields = [_field("email", "email")]
        self.assertEqual(
            validate_answers_against_schema(fields, {"email": "a@b.com"}), {}
        )

    def test_invalid(self):
        fields = [_field("email", "email")]
        for bad in ["notanemail", "@", "foo@", "foo@bar"]:
            errors = validate_answers_against_schema(fields, {"email": bad})
            self.assertIn("email", errors, f"Expected error for '{bad}'")


class TestPhoneValidation(SimpleTestCase):
    def test_valid(self):
        fields = [_field("phone", "phone")]
        for good in ["1234567890", "(123) 456-7890", "+1 555 123 4567"]:
            self.assertEqual(
                validate_answers_against_schema(fields, {"phone": good}), {}
            )

    def test_invalid(self):
        fields = [_field("phone", "phone")]
        errors = validate_answers_against_schema(fields, {"phone": "abc"})
        self.assertIn("phone", errors)

    def test_too_short(self):
        fields = [_field("phone", "phone", validations={"min_length": 10})]
        errors = validate_answers_against_schema(fields, {"phone": "12345"})
        self.assertIn("phone", errors)


class TestNumberValidation(SimpleTestCase):
    def test_valid_int(self):
        fields = [_field("age", "number")]
        self.assertEqual(validate_answers_against_schema(fields, {"age": 25}), {})

    def test_valid_float(self):
        fields = [_field("rate", "number")]
        self.assertEqual(
            validate_answers_against_schema(fields, {"rate": 19.99}), {}
        )

    def test_string_number(self):
        fields = [_field("age", "number")]
        self.assertEqual(validate_answers_against_schema(fields, {"age": "25"}), {})

    def test_invalid(self):
        fields = [_field("age", "number")]
        errors = validate_answers_against_schema(fields, {"age": "abc"})
        self.assertIn("age", errors)

    def test_min_value(self):
        fields = [_field("age", "number", validations={"min_value": 18})]
        errors = validate_answers_against_schema(fields, {"age": 16})
        self.assertIn("age", errors)

    def test_max_value(self):
        fields = [_field("age", "number", validations={"max_value": 100})]
        errors = validate_answers_against_schema(fields, {"age": 150})
        self.assertIn("age", errors)


class TestCheckboxValidation(SimpleTestCase):
    def test_valid_true(self):
        fields = [_field("agree", "checkbox", required=True)]
        self.assertEqual(
            validate_answers_against_schema(fields, {"agree": True}), {}
        )

    def test_required_but_false(self):
        fields = [_field("agree", "checkbox", required=True)]
        errors = validate_answers_against_schema(fields, {"agree": False})
        self.assertIn("agree", errors)

    def test_optional_false(self):
        fields = [_field("agree", "checkbox", required=False)]
        self.assertEqual(
            validate_answers_against_schema(fields, {"agree": False}), {}
        )

    def test_non_bool(self):
        fields = [_field("agree", "checkbox")]
        errors = validate_answers_against_schema(fields, {"agree": "yes"})
        self.assertIn("agree", errors)


class TestSelectValidation(SimpleTestCase):
    def test_valid(self):
        opts = [{"label": "A", "value": "a"}, {"label": "B", "value": "b"}]
        fields = [_field("choice", "select", options=opts)]
        self.assertEqual(
            validate_answers_against_schema(fields, {"choice": "a"}), {}
        )

    def test_invalid_option(self):
        opts = [{"label": "A", "value": "a"}]
        fields = [_field("choice", "select", options=opts)]
        errors = validate_answers_against_schema(fields, {"choice": "z"})
        self.assertIn("choice", errors)

    def test_non_string(self):
        opts = [{"label": "A", "value": "a"}]
        fields = [_field("choice", "select", options=opts)]
        errors = validate_answers_against_schema(fields, {"choice": 1})
        self.assertIn("choice", errors)


class TestMultiSelectValidation(SimpleTestCase):
    def test_valid(self):
        opts = [
            {"label": "A", "value": "a"},
            {"label": "B", "value": "b"},
            {"label": "C", "value": "c"},
        ]
        fields = [_field("skills", "multi_select", options=opts)]
        self.assertEqual(
            validate_answers_against_schema(fields, {"skills": ["a", "b"]}), {}
        )

    def test_invalid_option(self):
        opts = [{"label": "A", "value": "a"}]
        fields = [_field("skills", "multi_select", options=opts)]
        errors = validate_answers_against_schema(fields, {"skills": ["a", "z"]})
        self.assertIn("skills", errors)

    def test_not_a_list(self):
        fields = [_field("skills", "multi_select")]
        errors = validate_answers_against_schema(fields, {"skills": "a"})
        self.assertIn("skills", errors)

    def test_min_selections(self):
        opts = [{"label": "A", "value": "a"}, {"label": "B", "value": "b"}]
        fields = [
            _field(
                "skills",
                "multi_select",
                options=opts,
                validations={"min_selections": 2},
            )
        ]
        errors = validate_answers_against_schema(fields, {"skills": ["a"]})
        self.assertIn("skills", errors)

    def test_max_selections(self):
        opts = [
            {"label": "A", "value": "a"},
            {"label": "B", "value": "b"},
            {"label": "C", "value": "c"},
        ]
        fields = [
            _field(
                "skills",
                "multi_select",
                options=opts,
                validations={"max_selections": 1},
            )
        ]
        errors = validate_answers_against_schema(fields, {"skills": ["a", "b"]})
        self.assertIn("skills", errors)


class TestRadioValidation(SimpleTestCase):
    def test_valid(self):
        opts = [{"label": "Yes", "value": "yes"}, {"label": "No", "value": "no"}]
        fields = [_field("available", "radio", options=opts)]
        self.assertEqual(
            validate_answers_against_schema(fields, {"available": "yes"}), {}
        )

    def test_invalid(self):
        opts = [{"label": "Yes", "value": "yes"}]
        fields = [_field("available", "radio", options=opts)]
        errors = validate_answers_against_schema(
            fields, {"available": "maybe"}
        )
        self.assertIn("available", errors)


class TestDateValidation(SimpleTestCase):
    def test_valid(self):
        fields = [_field("start_date", "date")]
        self.assertEqual(
            validate_answers_against_schema(
                fields, {"start_date": "2025-06-15"}
            ),
            {},
        )

    def test_invalid_format(self):
        fields = [_field("start_date", "date")]
        errors = validate_answers_against_schema(
            fields, {"start_date": "15/06/2025"}
        )
        self.assertIn("start_date", errors)

    def test_invalid_date(self):
        fields = [_field("start_date", "date")]
        errors = validate_answers_against_schema(
            fields, {"start_date": "not-a-date"}
        )
        self.assertIn("start_date", errors)


class TestUrlValidation(SimpleTestCase):
    def test_valid(self):
        fields = [_field("website", "url")]
        self.assertEqual(
            validate_answers_against_schema(
                fields, {"website": "https://example.com"}
            ),
            {},
        )

    def test_invalid(self):
        fields = [_field("website", "url")]
        for bad in ["not-a-url", "ftp://example.com", "example.com"]:
            errors = validate_answers_against_schema(fields, {"website": bad})
            self.assertIn("website", errors, f"Expected error for '{bad}'")


class TestFileUploadValidation(SimpleTestCase):
    def test_valid_string(self):
        fields = [_field("resume", "file_upload")]
        self.assertEqual(
            validate_answers_against_schema(fields, {"resume": "resume.pdf"}), {}
        )

    def test_valid_dict(self):
        fields = [_field("resume", "file_upload")]
        self.assertEqual(
            validate_answers_against_schema(
                fields,
                {
                    "resume": {
                        "filename": "resume.pdf",
                        "url": "/uploads/resume.pdf",
                    }
                },
            ),
            {},
        )

    def test_dict_missing_filename(self):
        fields = [_field("resume", "file_upload")]
        errors = validate_answers_against_schema(
            fields, {"resume": {"url": "/x"}}
        )
        self.assertIn("resume", errors)

    def test_disallowed_extension(self):
        fields = [
            _field(
                "resume",
                "file_upload",
                validations={"allowed_extensions": [".pdf", ".docx"]},
            )
        ]
        errors = validate_answers_against_schema(
            fields, {"resume": "resume.exe"}
        )
        self.assertIn("resume", errors)

    def test_allowed_extension(self):
        fields = [
            _field(
                "resume",
                "file_upload",
                validations={"allowed_extensions": [".pdf"]},
            )
        ]
        self.assertEqual(
            validate_answers_against_schema(fields, {"resume": "resume.pdf"}),
            {},
        )


class TestUnknownFields(SimpleTestCase):
    def test_unknown_field_flagged(self):
        fields = [_field("name", "text")]
        errors = validate_answers_against_schema(
            fields, {"name": "Alice", "hacker_field": "payload"}
        )
        self.assertIn("hacker_field", errors)
        self.assertIn("Unknown", errors["hacker_field"][0])


class TestMixedValidation(SimpleTestCase):
    def test_full_form(self):
        fields = [
            _field("full_name", "text", required=True, validations={"min_length": 2}),
            _field("email", "email", required=True),
            _field("phone", "phone", required=False),
            _field(
                "years_exp",
                "number",
                validations={"min_value": 0, "max_value": 50},
            ),
            _field(
                "services",
                "multi_select",
                options=[
                    {"label": "Standard", "value": "standard"},
                    {"label": "Deep", "value": "deep"},
                    {"label": "Move-out", "value": "move_out"},
                ],
                validations={"min_selections": 1},
            ),
            _field("agree_terms", "checkbox", required=True),
            _field("start_date", "date"),
            _field("notes", "textarea"),
        ]
        answers = {
            "full_name": "Alice Smith",
            "email": "alice@example.com",
            "years_exp": 5,
            "services": ["standard", "deep"],
            "agree_terms": True,
            "start_date": "2025-07-01",
            "notes": "Looking forward to it.",
        }
        self.assertEqual(validate_answers_against_schema(fields, answers), {})

    def test_full_form_with_errors(self):
        fields = [
            _field("full_name", "text", required=True),
            _field("email", "email", required=True),
            _field(
                "service_type",
                "select",
                required=True,
                options=[{"label": "A", "value": "a"}],
            ),
        ]
        answers = {
            "email": "not-valid",
            "service_type": "invalid_choice",
        }
        errors = validate_answers_against_schema(fields, answers)
        self.assertIn("full_name", errors)
        self.assertIn("email", errors)
        self.assertIn("service_type", errors)
