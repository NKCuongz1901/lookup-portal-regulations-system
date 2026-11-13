"""Structured Gemini output. Source coordinates are resolved by the backend."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Quote(StrictModel):
    segment_index: StrictInt = Field(ge=0)
    quote: str = Field(min_length=1, max_length=60000, description="Exact substring of the segment content; preserve OCR, spaces and newlines.")
    occurrence: StrictInt = Field(default=0, ge=0, description="Zero-based occurrence of this exact quote within this segment.")


class Attributed(StrictModel):
    value_evidence: list[Quote] = Field(min_length=1, max_length=20)
    context_evidence: list[Quote] = Field(default_factory=list, max_length=20)


def iso_date(value: str | None) -> str | None:
    if value is not None and date.fromisoformat(value).isoformat() != value:
        raise ValueError("Expected YYYY-MM-DD")
    return value


class DeadlineValue(StrictModel):
    kind: Literal["absolute", "date_range", "relative", "recurring"]
    date: str | None = None
    boundary: Literal["before", "on_or_before"] | None = None
    start_date: str | None = None
    end_date: str | None = None
    amount: StrictInt | None = Field(default=None, gt=0)
    unit: Literal["day", "week", "month", "year"] | None = None
    working_days: bool | None = None
    anchor_text: str | None = None
    position: str | None = None
    period: str | None = None

    _dates = field_validator("date", "start_date", "end_date")(iso_date)

    @model_validator(mode="after")
    def consistent(self):
        required = {"absolute": ("date", "boundary"), "date_range": ("start_date", "end_date"),
                    "relative": ("amount", "unit"), "recurring": ("position", "period")}[self.kind]
        missing = [key for key in required if getattr(self, key) in (None, "")]
        if missing:
            raise ValueError(f"{self.kind} deadline requires: {', '.join(missing)}; omit the candidate if not supported by source")
        if self.kind == "date_range" and self.start_date > self.end_date:
            raise ValueError("Reversed date interval")
        allowed = {"absolute": {"date", "boundary"}, "date_range": {"start_date", "end_date"},
                   "relative": {"amount", "unit", "working_days", "anchor_text"},
                   "recurring": {"position", "period"}}[self.kind]
        conflicting = [key for key, value in self.model_dump().items() if value is not None and key not in allowed | {"kind"}]
        if conflicting:
            raise ValueError(f"For {self.kind}, set these unrelated details to null: {', '.join(conflicting)}")
        return self


class ObligationValue(StrictModel):
    subject: str | None = None
    requirement: str = Field(min_length=1)


class SubjectValue(StrictModel):
    text: str = Field(min_length=1)


class LegalBasisValue(StrictModel):
    document_type: Literal["code", "law", "decree", "circular", "decision", "regulation", "plan", "other"]
    document_number: str | None = None
    issue_date: str | None = None
    reference_text: str = Field(min_length=1)

    _date = field_validator("issue_date")(iso_date)


class Deadline(Attributed):
    normalized_value: DeadlineValue


class Obligation(Attributed):
    normalized_value: ObligationValue


class Subject(Attributed):
    normalized_value: SubjectValue


class LegalBasis(Attributed):
    normalized_value: LegalBasisValue


class GeminiOutput(StrictModel):
    deadlines: list[Deadline] = Field(max_length=200)
    obligations: list[Obligation] = Field(max_length=200)
    applicable_subjects: list[Subject] = Field(max_length=200)
    legal_bases: list[LegalBasis] = Field(max_length=200)


def response_schema() -> dict:
    """Send the portable JSON Schema subset; enforce bounds locally with Pydantic.

    Provider schema compilers differ in their support for length/default/numeric
    constraints. These are validation rules, not instructions to trust output.
    """
    supported = {"$defs", "$ref", "type", "properties", "required", "items", "anyOf", "enum", "description"}

    def portable(value):
        if isinstance(value, list):
            return [portable(item) for item in value]
        if not isinstance(value, dict):
            return value
        return {key: ({name: portable(schema) for name, schema in item.items()}
                      if key in {"properties", "$defs"} else portable(item))
                for key, item in value.items() if key in supported}

    return portable(GeminiOutput.model_json_schema())
