from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, Field, field_validator


class MatchCreate(BaseModel):
    venue_id: int
    title: str = Field(min_length=3, max_length=100)
    starts_at: datetime
    capacity: int = Field(ge=2, le=30)
    organizer_name: str = Field(min_length=2, max_length=50)

    @field_validator("starts_at")
    @classmethod
    def validate_start(cls, value):
        if value.tzinfo is None:
            raise ValueError("Informe data e hora com fuso horário.")
        now = datetime.now(timezone.utc)
        if value <= now or value > now + timedelta(days=7):
            raise ValueError("A partida deve ocorrer nos próximos sete dias.")
        return value


class AttendanceCreate(BaseModel):
    display_name: str = Field(min_length=2, max_length=50)


class VenueInput(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    address: str = Field(default="", max_length=240)
