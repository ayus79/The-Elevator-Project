import logging
import random
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from logic import BuildingService, ControllerService, ElevatorService
from schemas import Building, CarCall, Controller, Direction, Elevator, HallCall


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="The Elevator Project")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


# ============== date-wise logging ================

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("elevator")
logger.setLevel(logging.INFO)

_file_handler = TimedRotatingFileHandler(
    LOG_DIR / "elevator.log",
    when="midnight",
    backupCount=30,
    encoding="utf-8",
)
_file_handler.suffix = "%Y-%m-%d"
_file_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
)
logger.addHandler(_file_handler)

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
)
logger.addHandler(_console_handler)


# ============== in-memory simulation state ================


def make_default_building() -> Building:
    return Building(
        num_floors=10,
        controller=Controller(
            elevators=[
                Elevator(id=1, current_floor=1, capacity=8),
                Elevator(id=2, current_floor=1, capacity=8),
                Elevator(id=3, current_floor=1, capacity=8),
            ]
        ),
    )


building = make_default_building()


# ============== request bodies ================


class SetupRequest(BaseModel):
    num_floors: int = Field(ge=1)
    num_elevators: int = Field(ge=1)
    capacity: int = Field(default=8, gt=0)


class BoardRequest(BaseModel):
    passengers: int = Field(default=1, gt=0)


class RandomCallResult(BaseModel):
    hall_call: HallCall
    elevator_id: int
    boarded: int
    destination_floor: int
    building: dict


# ============== view ================


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"building": building},
    )


# ============== api: state ================


@app.get("/api/state")
def get_state():
    return building.model_dump()


@app.post("/api/reset")
def reset_building(req: SetupRequest):
    global building
    new_building = Building(
        num_floors=req.num_floors,
        controller=Controller(
            elevators=[
                Elevator(id=i + 1, current_floor=1, capacity=req.capacity)
                for i in range(req.num_elevators)
            ]
        ),
    )
    try:
        ControllerService.validate_unique_ids(new_building.controller)
        BuildingService.validate_elevators_within_range(new_building)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    building = new_building
    logger.info(
        "RESET building floors=%d elevators=%d capacity=%d",
        req.num_floors,
        req.num_elevators,
        req.capacity,
    )
    return building.model_dump()


# ============== api: calls ================


@app.post("/api/hall-call")
def submit_hall_call(call: HallCall):
    if not (1 <= call.floor <= building.num_floors):
        raise HTTPException(400, f"Floor must be within [1, {building.num_floors}]")
    try:
        elevator = ControllerService.submit_hall_call(building.controller, call)
    except ValueError as exc:
        logger.warning(
            "HALL-CALL rejected floor=%d direction=%s error=%s",
            call.floor,
            call.direction.value,
            exc,
        )
        raise HTTPException(400, str(exc)) from exc
    logger.info(
        "HALL-CALL floor=%d direction=%s -> elevator=%d",
        call.floor,
        call.direction.value,
        elevator.id,
    )
    return elevator.model_dump()


@app.post("/api/car-call")
def submit_car_call(call: CarCall):
    if not (1 <= call.floor <= building.num_floors):
        raise HTTPException(400, f"Floor must be within [1, {building.num_floors}]")
    try:
        ControllerService.submit_car_call(building.controller, call)
        elevator = ControllerService.get_elevator(building.controller, call.elevator_id)
    except ValueError as exc:
        logger.warning(
            "CAR-CALL rejected elevator=%d floor=%d error=%s",
            call.elevator_id,
            call.floor,
            exc,
        )
        raise HTTPException(400, str(exc)) from exc
    logger.info("CAR-CALL elevator=%d floor=%d", call.elevator_id, call.floor)
    return elevator.model_dump()


# ============== api: simulation ================


@app.post("/api/step")
def step_simulation():
    ControllerService.step(building.controller)
    logger.info(
        "STEP %s",
        ", ".join(
            f"elevator={e.id} floor={e.current_floor} dir={e.direction.value} door={e.door_state.value}"
            for e in building.controller.elevators
        ),
    )
    return building.model_dump()


@app.post("/api/random-call", response_model=RandomCallResult)
def random_call():
    """Generate a random passenger request: a hall call from a random floor,
    boarding a random number of passengers, and a random destination car call.
    """
    origin = random.randint(1, building.num_floors)
    if origin == building.num_floors:
        direction = Direction.DOWN
    elif origin == 1:
        direction = Direction.UP
    else:
        direction = random.choice([Direction.UP, Direction.DOWN])

    call = HallCall(floor=origin, direction=direction)
    try:
        elevator = ControllerService.submit_hall_call(building.controller, call)
    except ValueError as exc:
        logger.warning(
            "RANDOM-CALL rejected floor=%d direction=%s error=%s",
            origin,
            direction.value,
            exc,
        )
        raise HTTPException(400, str(exc)) from exc

    room_left = elevator.capacity - elevator.load
    boarded = random.randint(1, max(1, min(3, room_left))) if room_left > 0 else 0
    if boarded:
        ElevatorService.board(elevator, boarded)

    if direction == Direction.UP:
        destination = random.randint(origin + 1, building.num_floors)
    else:
        destination = random.randint(1, origin - 1)

    car_call = CarCall(elevator_id=elevator.id, floor=destination)
    ControllerService.submit_car_call(building.controller, car_call)

    logger.info(
        "RANDOM-CALL floor=%d direction=%s -> elevator=%d boarded=%d destination=%d",
        origin,
        direction.value,
        elevator.id,
        boarded,
        destination,
    )

    return RandomCallResult(
        hall_call=call,
        elevator_id=elevator.id,
        boarded=boarded,
        destination_floor=destination,
        building=building.model_dump(),
    )


# ============== api: boarding ================


@app.post("/api/elevator/{elevator_id}/board")
def board(elevator_id: int, req: BoardRequest):
    try:
        elevator = ControllerService.get_elevator(building.controller, elevator_id)
        ElevatorService.board(elevator, req.passengers)
    except ValueError as exc:
        logger.warning(
            "BOARD rejected elevator=%d passengers=%d error=%s",
            elevator_id,
            req.passengers,
            exc,
        )
        raise HTTPException(400, str(exc)) from exc
    logger.info(
        "BOARD elevator=%d passengers=%d load=%d",
        elevator_id,
        req.passengers,
        elevator.load,
    )
    return elevator.model_dump()


@app.post("/api/elevator/{elevator_id}/alight")
def alight(elevator_id: int, req: BoardRequest):
    try:
        elevator = ControllerService.get_elevator(building.controller, elevator_id)
        ElevatorService.alight(elevator, req.passengers)
    except ValueError as exc:
        logger.warning(
            "ALIGHT rejected elevator=%d passengers=%d error=%s",
            elevator_id,
            req.passengers,
            exc,
        )
        raise HTTPException(400, str(exc)) from exc
    logger.info(
        "ALIGHT elevator=%d passengers=%d load=%d",
        elevator_id,
        req.passengers,
        elevator.load,
    )
    return elevator.model_dump()
