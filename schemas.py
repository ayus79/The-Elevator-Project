from enum import Enum
from pydantic import BaseModel, Field, field_validator


# ============== enum ================


class Direction(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    IDLE = "IDLE"


class DoorState(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


# ============== calls ================


class HallCall(BaseModel):
    floor: int
    direction: Direction

    @field_validator("direction")
    @classmethod
    def direction_must_not_be_idle(cls, v: Direction) -> Direction:
        if v == Direction.IDLE:
            raise ValueError("A hall call must be UP or DOWN, not IDLE")
        return v


class CarCall(BaseModel):
    elevator_id: int
    floor: int


# ============== elevator ================


class Elevator(BaseModel):
    model_config = {"validate_assignment": True}

    id: int
    current_floor: int
    direction: Direction = Direction.IDLE
    door_state: DoorState = DoorState.CLOSED
    capacity: int = Field(gt=0)
    load: int = Field(default=0, ge=0)
    up_stops: set[int] = Field(default_factory=set)
    down_stops: set[int] = Field(default_factory=set)


class Controller(BaseModel):
    model_config = {"validate_assignment": True}

    elevators: list[Elevator] = Field(min_length=1)


class Building(BaseModel):
    num_floors: int = Field(ge=1)
    controller: Controller
