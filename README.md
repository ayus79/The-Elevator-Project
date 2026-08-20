# The Elevator Project

## What this is

A simulator for how a building's elevators decide who picks you up. You set
the number of floors, elevators, and elevator capacity, then call an elevator
from any floor — the system figures out which elevator should answer, moves
it there floor by floor, and lets passengers board/alight along the way.

## Why

Elevator dispatch is a small but real scheduling problem: several elevators,
one request, pick the one that gets there fastest without wasting the other
elevators' current trips. This project works through that logic from
scratch and wraps it in a web UI so the decision-making is visible instead of
buried in test assertions.

## How it works

- **`schemas.py`** — the data: a `Building` has a `Controller`, which holds a
  list of `Elevator`s. Each elevator tracks its floor, direction, door state,
  load, and the set of floors it still needs to stop at.
- **`logic.py`** — the brain. When a hall call comes in (`floor` + `UP`/`DOWN`),
  it scores every elevator and picks the best one, in order of preference:
  1. an elevator already heading that way and not past the floor yet,
  2. otherwise the nearest idle elevator,
  3. otherwise the nearest elevator overall (it'll finish its current trip
     and reverse).
  A `step()` function then moves every elevator one floor at a time, opening
  its doors whenever it reaches a stop.
- **`main.py`** — a FastAPI server that holds one `Building` in memory and
  exposes it as an API (call an elevator, step the simulation, board/alight
  passengers, or fire random traffic to watch it run on its own). Every
  action is also written to a dated log file in `logs/`.
- **`templates/` + `static/`** — the browser UI: a Jinja page showing each
  elevator as a moving car in its shaft, with buttons for hall calls, car
  calls, boarding, and stepping.

## Running it

```bash
python -m venv env
source env/bin/activate
pip install -r requirements.txt
uvicorn main:app --port 8000 --workers 1 --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Set up the building,
click "Call" from a floor, and either click "Step" manually or turn on
auto-step / random traffic to watch it play out.
