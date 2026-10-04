from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Evidence(StrictModel):
    source_id: Literal['resume', 'reviewer']
    quote: str = Field(min_length=1, max_length=1000)

class Candidate(StrictModel):
    # Matching excludes names, age, gender, race, and other irrelevant identity fields.
    years_experience: float | None = Field(default=None, ge=0, le=60)
    license_number: str | None = Field(default=None, max_length=100)
    license_state: str | None = Field(default=None, pattern=r'^[A-Z]{2}$')
    evidence: dict[str, Evidence] = Field(default_factory=dict)

class AssessmentRequest(StrictModel):
    resume_text: str = Field(min_length=10, max_length=30000)
    job_id: Literal['rn-icu', 'rn-general'] = 'rn-icu'

class ReviewRequest(StrictModel):
    action: Literal['clarify', 'approve', 'reject']
    notes: str = Field(min_length=3, max_length=2000)
    corrections: dict[str, str | float] = Field(default_factory=dict)
    expected_version: int = Field(ge=0)

    @model_validator(mode='after')
    def corrections_are_scoped(self):
        if set(self.corrections) - {'years_experience', 'license_number', 'license_state'}:
            raise ValueError('Only documented candidate fields may be corrected')
        if self.action != 'clarify' and self.corrections:
            raise ValueError('Corrections require the clarify action')
        return self

class Summary(StrictModel):
    text: str
    rule_ids: list[str]
    policy_ids: list[str]
    recommendation: Literal['REQUIREMENTS_MET', 'REQUIREMENTS_NOT_MET', 'VERIFICATION_PENDING']
    registry_mode: Literal['SIMULATED'] = 'SIMULATED'
