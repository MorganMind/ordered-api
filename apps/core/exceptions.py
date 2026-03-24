class TechnicianNotEligibleError(Exception):
    """Raised by technician onboarding / eligibility checks."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args or ("Technician is not eligible.",))
        self.onboarding_status = kwargs.get("onboarding_status")
        self.missing_fields = kwargs.get("missing_fields") or []
        self.suspension_reason = kwargs.get("suspension_reason") or ""
