const els = {
  shaftView: document.getElementById("shaft-view"),
  statusBody: document.querySelector("#status-table tbody"),
  ccElevator: document.getElementById("cc-elevator"),
  bdElevator: document.getElementById("bd-elevator"),
  errorBanner: document.getElementById("error-banner"),
  cfgFloors: document.getElementById("cfg-floors"),
  cfgElevators: document.getElementById("cfg-elevators"),
  cfgCapacity: document.getElementById("cfg-capacity"),
  cfgAuto: document.getElementById("cfg-auto"),
  cfgRandom: document.getElementById("cfg-random"),
};

let autoTimer = null;
let randomTimer = null;

function showError(message) {
  els.errorBanner.textContent = message;
  els.errorBanner.hidden = false;
  clearTimeout(showError._t);
  showError._t = setTimeout(() => { els.errorBanner.hidden = true; }, 4000);
}

async function api(path, options) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const message = data?.detail ?? `Request failed (${res.status})`;
    showError(message);
    throw new Error(message);
  }
  return data;
}

function renderShafts(building) {
  const { num_floors, controller } = building;
  els.shaftView.innerHTML = "";

  for (const elevator of controller.elevators) {
    const wrap = document.createElement("div");
    wrap.className = "shaft-wrap";

    const shaft = document.createElement("div");
    shaft.className = "shaft";

    for (let floor = 1; floor <= num_floors; floor++) {
      const cell = document.createElement("div");
      cell.className = "floor-cell";

      const label = document.createElement("span");
      label.className = "floor-label";
      label.textContent = floor;
      cell.appendChild(label);

      if (elevator.current_floor === floor) {
        const car = document.createElement("div");
        car.className = `car dir-${elevator.direction} door-${elevator.door_state}`;
        car.textContent = `#${elevator.id}`;
        cell.appendChild(car);
      }

      shaft.appendChild(cell);
    }

    const name = document.createElement("div");
    name.className = "shaft-name";
    name.textContent = `Elevator ${elevator.id}`;

    wrap.appendChild(shaft);
    wrap.appendChild(name);
    els.shaftView.appendChild(wrap);
  }
}

function renderStatusTable(building) {
  els.statusBody.innerHTML = "";
  for (const e of building.controller.elevators) {
    const row = document.createElement("tr");
    const stops = [...e.up_stops, ...e.down_stops].sort((a, b) => a - b).join(", ") || "-";
    row.innerHTML = `
      <td>${e.id}</td>
      <td>${e.current_floor}</td>
      <td>${e.direction}</td>
      <td>${e.door_state}</td>
      <td>${e.load}/${e.capacity}</td>
      <td>${stops}</td>
    `;
    els.statusBody.appendChild(row);
  }
}

function renderElevatorSelects(building) {
  for (const select of [els.ccElevator, els.bdElevator]) {
    const prev = select.value;
    select.innerHTML = "";
    for (const e of building.controller.elevators) {
      const opt = document.createElement("option");
      opt.value = e.id;
      opt.textContent = `Elevator ${e.id}`;
      select.appendChild(opt);
    }
    if (prev) select.value = prev;
  }
}

function render(building) {
  renderShafts(building);
  renderStatusTable(building);
  renderElevatorSelects(building);
}

async function refresh() {
  const building = await api("/api/state");
  render(building);
}

document.getElementById("btn-reset").addEventListener("click", async () => {
  const building = await api("/api/reset", {
    method: "POST",
    body: JSON.stringify({
      num_floors: Number(els.cfgFloors.value),
      num_elevators: Number(els.cfgElevators.value),
      capacity: Number(els.cfgCapacity.value),
    }),
  });
  render(building);
});

document.getElementById("btn-step").addEventListener("click", async () => {
  const building = await api("/api/step", { method: "POST" });
  render(building);
});

els.cfgAuto.addEventListener("change", () => {
  if (els.cfgAuto.checked) {
    autoTimer = setInterval(async () => {
      const building = await api("/api/step", { method: "POST" }).catch(() => null);
      if (building) render(building);
    }, 800);
  } else {
    clearInterval(autoTimer);
  }
});

els.cfgRandom.addEventListener("change", () => {
  if (els.cfgRandom.checked) {
    if (!els.cfgAuto.checked) {
      els.cfgAuto.checked = true;
      els.cfgAuto.dispatchEvent(new Event("change"));
    }
    randomTimer = setInterval(async () => {
      const result = await api("/api/random-call", { method: "POST" }).catch(() => null);
      if (!result) return;
      render(result.building);
    }, 2500);
  } else {
    clearInterval(randomTimer);
  }
});

document.getElementById("hc-up").addEventListener("click", async () => {
  const floor = Number(document.getElementById("hc-floor").value);
  await api("/api/hall-call", {
    method: "POST",
    body: JSON.stringify({ floor, direction: "UP" }),
  }).catch(() => null);
  await refresh();
});

document.getElementById("hc-down").addEventListener("click", async () => {
  const floor = Number(document.getElementById("hc-floor").value);
  await api("/api/hall-call", {
    method: "POST",
    body: JSON.stringify({ floor, direction: "DOWN" }),
  }).catch(() => null);
  await refresh();
});

document.getElementById("cc-submit").addEventListener("click", async () => {
  const elevator_id = Number(els.ccElevator.value);
  const floor = Number(document.getElementById("cc-floor").value);
  await api("/api/car-call", {
    method: "POST",
    body: JSON.stringify({ elevator_id, floor }),
  }).catch(() => null);
  await refresh();
});

document.getElementById("bd-board").addEventListener("click", async () => {
  const id = Number(els.bdElevator.value);
  const passengers = Number(document.getElementById("bd-passengers").value);
  await api(`/api/elevator/${id}/board`, {
    method: "POST",
    body: JSON.stringify({ passengers }),
  }).catch(() => null);
  await refresh();
});

document.getElementById("bd-alight").addEventListener("click", async () => {
  const id = Number(els.bdElevator.value);
  const passengers = Number(document.getElementById("bd-passengers").value);
  await api(`/api/elevator/${id}/alight`, {
    method: "POST",
    body: JSON.stringify({ passengers }),
  }).catch(() => null);
  await refresh();
});

refresh();
