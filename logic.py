"""
n = number of floors
m = number of elevators
c = capacity limit
tt = travel time per floor
dt = door open/close time
hc = hall call
cc = car call

Direction: UP, DOWN, IDLE
DoorState: OPEN, CLOSED

Elevator:
  id, current_floor, direction, door_state, capacity, load
  up_stops   -> sorted set of floors to visit while going up
  down_stops -> sorted set of floors to visit while going down

Controller (Dispatcher):
  elevators: list[Elevator]
  submit_hall_call(floor, direction)
  submit_car_call(elevator_id, floor)
  choose_elevator(floor, direction) -> Elevator

Building:
  num_floors, elevators, controller
"""

from typing import Optional
from schemas import (
    Building,
    Direction,
    DoorState,
    Elevator,
    Controller,
    HallCall,
    CarCall,
)


class ElevatorService:

    def next_up_stop(elevator: Elevator) -> Optional[int]:
        candidates = [f for f in elevator.up_stops if f >= elevator.current_floor]
        return min(candidates) if candidates else None

    def next_down_stop(elevator: Elevator) -> Optional[int]:
        candidates = [f for f in elevator.down_stops if f <= elevator.current_floor]
        return max(candidates) if candidates else None

    def is_idle(elevator: Elevator) -> bool:
        return (
            elevator.direction == Direction.IDLE
            and not elevator.up_stops
            and not elevator.down_stops
        )

    def has_room(elevator: Elevator, incoming: int = 1) -> bool:
        return elevator.load + incoming <= elevator.capacity

    def board(elevator: Elevator, passengers: int = 1) -> None:
        if not ElevatorService.has_room(elevator, passengers):
            raise ValueError(f"Elevator {elevator.id} is full")

        elevator.load += passengers

    def alight(elevator: Elevator, passengers: int = 1) -> None:
        if passengers > elevator.load:
            raise ValueError(
                f"Elevator {elevator.id} cannot unload more than current load."
            )

        elevator.load -= passengers


class ControllerService:

    def validate_unique_ids(controller: Controller) -> None:
        ids = [e.id for e in controller.elevators]
        if len(ids) != len(set(ids)):
            raise ValueError("Elevator ids must be unique.")

    def get_elevator(controller: Controller, elevator_id: int) -> Elevator:
        for e in controller.elevators:
            if e.id == elevator_id:
                return e

        raise ValueError("No elevator found.")

    def choose_elevator(controller: Controller, call: HallCall) -> Elevator:
        best: Optional[Elevator] = None
        best_score: Optional[tuple[int, int]] = None

        for e in controller.elevators:
            distance = abs(e.current_floor - call.floor)

            if e.direction == call.direction and ElevatorService.has_room(e):
                if call.direction == Direction.UP and e.current_floor <= call.floor:
                    score = (0, distance)
                elif call.direction == Direction.DOWN and e.current_floor >= call.floor:
                    score = (0, distance)
                else:
                    score = (2, distance)
            elif ElevatorService.is_idle(e):
                score = (1, distance)
            else:
                score = (2, distance)

            if best_score is None or score < best_score:
                best = e
                best_score = score

        if best is None:
            raise ValueError("No elevator available to serve this call.")

        return best

    def submit_hall_call(controller: Controller, call: HallCall) -> Elevator:
        elevator = ControllerService.choose_elevator(controller, call)

        if call.floor > elevator.current_floor:
            elevator.up_stops.add(call.floor)
        elif call.floor < elevator.current_floor:
            elevator.down_stops.add(call.floor)

        if (
            elevator.direction == Direction.IDLE
            and call.floor != elevator.current_floor
        ):
            elevator.direction = (
                Direction.UP if call.floor > elevator.current_floor else Direction.DOWN
            )

        return elevator

    def submit_car_call(controller: Controller, call: CarCall) -> None:
        elevator = ControllerService.get_elevator(controller, call.elevator_id)

        if call.floor > elevator.current_floor:
            elevator.up_stops.add(call.floor)
        elif call.floor < elevator.current_floor:
            elevator.down_stops.add(call.floor)

        if (
            elevator.direction == Direction.IDLE
            and call.floor != elevator.current_floor
        ):
            elevator.direction = (
                Direction.UP if call.floor > elevator.current_floor else Direction.DOWN
            )

    def step(controller: Controller) -> None:
        for e in controller.elevators:
            ControllerService._step_elevator(e)

    def _step_elevator(e: Elevator) -> None:
        if e.direction == Direction.UP:
            next_stop = ElevatorService.next_up_stop(e)
            if next_stop is None:
                e.direction = Direction.DOWN if e.down_stops else Direction.IDLE
                return
            if e.current_floor == next_stop:
                e.up_stops.discard(next_stop)
                e.door_state = DoorState.OPEN
                remaining = ElevatorService.next_up_stop(e)
                if remaining is None:
                    e.direction = Direction.DOWN if e.down_stops else Direction.IDLE
            else:
                e.door_state = DoorState.CLOSED
                e.current_floor += 1

        elif e.direction == Direction.DOWN:
            next_stop = ElevatorService.next_down_stop(e)
            if next_stop is None:
                e.direction = Direction.UP if e.up_stops else Direction.IDLE
                return
            if e.current_floor == next_stop:
                e.down_stops.discard(next_stop)
                e.door_state = DoorState.OPEN
                remaining = ElevatorService.next_down_stop(e)
                if remaining is None:
                    e.direction = Direction.UP if e.up_stops else Direction.IDLE
            else:
                e.door_state = DoorState.CLOSED
                e.current_floor -= 1
        else:
            e.door_state = DoorState.CLOSED
            if e.up_stops:
                e.direction = Direction.UP
            elif e.down_stops:
                e.direction = Direction.DOWN


class BuildingService:

    def validate_elevators_within_range(building: Building) -> None:
        for e in building.controller.elevators:
            if not (1 <= e.current_floor <= building.num_floors):
                raise ValueError(
                    f"Elevator {e.id} current_floor={e.current_floor} "
                    f"is outside building range [1, {building.num_floors}]"
                )
