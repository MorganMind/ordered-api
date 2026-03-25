from __future__ import annotations

from .models import FormFieldType


FORM_TEMPLATES: tuple[dict, ...] = (
    {
        "key": "cleaning_technician_intake_v1",
        "name": "Cleaning Technician Application",
        "description": (
            "Application for cleaning roles: location, schedule, experience, "
            "and types of work."
        ),
        "default_title": "Apply to join our team",
        "default_form_description": (
            "We’re glad you’re interested. Answer a few questions so we can "
            "learn about you and how you’d like to work with us."
        ),
        "fields_schema": [
            {
                "field_key": "county",
                "label": "Which county or area are you closest to?",
                "description": (
                    "We use this to see if we have opportunities near you."
                ),
                "field_type": FormFieldType.TEXT,
                "required": True,
                "position": 0,
                "placeholder": "Example: Essex County, NJ",
                "validations": {"min_length": 2, "max_length": 120},
            },
            {
                "field_key": "availability",
                "label": "When are you usually available to work?",
                "description": "Select all that apply.",
                "field_type": FormFieldType.MULTI_SELECT,
                "required": True,
                "position": 1,
                "options": [
                    {"label": "Weekdays", "value": "weekdays"},
                    {"label": "Weekends", "value": "weekends"},
                    {"label": "Evenings", "value": "evenings"},
                    {"label": "Flexible", "value": "flexible"},
                ],
                "validations": {"min_selections": 1},
            },
            {
                "field_key": "hours_per_week",
                "label": "Roughly how many hours per week are you looking for?",
                "description": "Optional — skip if you’re not sure yet.",
                "field_type": FormFieldType.NUMBER,
                "required": False,
                "position": 2,
                "validations": {"min_value": 1, "max_value": 80},
            },
            {
                "field_key": "experience_summary",
                "label": "Tell us about your cleaning experience",
                "description": (
                    "A few sentences is enough — whatever you’d like us to know."
                ),
                "field_type": FormFieldType.TEXTAREA,
                "required": True,
                "position": 3,
                "validations": {"max_length": 1500},
            },
            {
                "field_key": "work_types",
                "label": "What kinds of cleaning work do you do?",
                "description": "Select all that apply.",
                "field_type": FormFieldType.MULTI_SELECT,
                "required": True,
                "position": 4,
                "options": [
                    {"label": "Standard home cleaning", "value": "standard_home_cleaning"},
                    {"label": "Deep cleaning", "value": "deep_cleaning"},
                    {"label": "Organizing", "value": "organizing"},
                    {"label": "Move-in / move-out", "value": "move_in_move_out"},
                    {"label": "Other", "value": "other"},
                ],
                "validations": {"min_selections": 1},
            },
        ],
    },
)


def list_form_templates() -> list[dict]:
    return [
        {
            "key": t["key"],
            "name": t["name"],
            "description": t["description"],
            "default_title": t["default_title"],
            "default_form_description": t["default_form_description"],
            "fields_schema": t["fields_schema"],
        }
        for t in FORM_TEMPLATES
    ]


def get_form_template(template_key: str) -> dict | None:
    for template in FORM_TEMPLATES:
        if template["key"] == template_key:
            return template
    return None
