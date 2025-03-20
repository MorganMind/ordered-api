from pydantic import BaseModel
# from organization.models.organization_type import OrganizationType

class OnboardingPayload(BaseModel):
    organization_name: str 
    # organization_type: OrganizationType

class JoinOrganizationOnboardingPayload(BaseModel):
    organization_id: str 