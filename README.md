# AGV Robotica

Automated Guided Vehicle (AGV) for warehouse pallet-trolley handling,
simulated in CoppeliaSim. Developed for the Intelligent Systems and
Robotics Laboratory (ISRLAB) course, A.Y. 2025/26, Università degli Studi
dell'Aquila — supervisor: Prof. Giovanni De Gasperis.

The AGV navigates a graph of named warehouse locations, couples to pallet
trolleys via a pincer-arm mechanism, and tows them to their destination,
under a priority-ordered mission queue managed by a Behavior Tree.

A full design and implementation report is maintained in a separate
documentation repository; this README covers installation and execution
of the code only.

## Architecture at a Glance

The system is split into three containerized services, communicating
through Redis:

- **`agv_brain`** — the deliberative layer: a Behavior Tree (`py_trees`)
  that plans missions, decides intersection routing, and monitors safety
  and battery constraints.
- **`agv_body`** — the reactive layer: bridges to CoppeliaSim via the
  `zmqRemoteApi`, reads sensors (color sensors, AprilTag, LiDAR, vision),
  and drives the wheel and pincer-arm actuators.
- **`agv_redis`** — the message broker and shared state: commands flow
  Brain→Body via pub/sub on `agv_command_channel`; sensor state flows
  Body→Brain via the `brain_memory` key.

A fourth service, `agv_vision` (YOLO-based person detection), is present
in `src/vision/` but currently disabled in `docker-compose.yml`.

## Prerequisites

- **Docker** and **Docker Compose** (v2, i.e. the `docker compose` CLI,
  not the legacy `docker-compose` standalone binary).
- **CoppeliaSim Edu**, version 4.10.0 or later, installed **on the host
  machine** (not inside a container) with the scene file open.
- The host must expose the CoppeliaSim `zmqRemoteApi` server on its
  default port (`23000`); this is enabled by default when a scene is
  running in CoppeliaSim.
- Linux/macOS/Windows with Docker configured to resolve
  `host.docker.internal` to the host (this is automatic on Docker
  Desktop; on native Linux Docker Engine, the `extra_hosts` entry in
  `docker-compose.yml` handles this via `host-gateway`).

## Repository Structure

```
agv_robotica/
|-- docker-compose.yml            # main orchestration file
|-- docker-compose.mock.yml        # override: run Brain against a mocked Body
|-- docker-compose.mockBrain.yml   # override: run Body against a mocked Brain
|-- src/
|   |-- brain/                     # Behavior Tree, mission planning, Redis interface
|   |   |-- main_brain.py
|   |   |-- mock_brain.py          # standalone mock, for testing the Body in isolation
|   |   |-- modules/
|   |   `-- requirements.txt
|   |-- body/                      # CoppeliaSim bridge: sensors, controllers, actuators
|   |   |-- main_body.py
|   |   |-- mock_body.py           # standalone mock, for testing the Brain in isolation
|   |   |-- modules/
|   |   |-- docs/node_map_id.json  # warehouse graph: location name → node ID
|   |   `-- requirements.txt
|   `-- vision/                    # YOLO person-detection pipeline (currently disabled)
|-- external_libs/                 # vendored CoppeliaSim zmqRemoteApi Python client
`-- docs/                          # architecture diagrams, FSM, operational guides
```

## Installation

1. Clone the repository:
   ```sh
   git clone https://github.com/andianno/agv_robotica.git
   cd agv_robotica
   ```
2. Start CoppeliaSim Edu on the host machine and open the project scene
   (see `docs/` for the scene file). Leave the simulation running (or at
   least loaded) before starting the containers — `agv_body` connects to
   it over the network as soon as it starts.
3. Build the images:
   ```sh
   docker compose build
   ```

## Running the Full System

```sh
docker compose up
```

This starts, in dependency order:

1. `agv_redis` — waits until healthy (`redis-cli ping`).
2. `agv_body` — waits for Redis to be healthy, then connects to
   CoppeliaSim on the host; reports itself healthy once it has created
   the `/tmp/body_ready` marker (connection to the simulator confirmed).
3. `agv_brain` — waits for **both** Redis and the Body to be healthy
   before issuing any command, so no mission command is ever sent before
   the Body is actually able to execute it.

To stop the system cleanly:

```sh
docker compose down
```

Each service is given a grace period to shut down safely on `SIGTERM`
(5 s for Redis, 30 s for the Body — long enough to bring the AGV to a
safe stop and close the CoppeliaSim connection without leaving it in a
stuck state).

To follow logs from all services:

```sh
docker compose logs -f
```

or a single one, e.g.:

```sh
docker compose logs -f agv_brain
```

## Testing Brain and Body in Isolation

Two Compose override files are provided to test one side of the
architecture without needing the other fully working, using the
`mock_brain.py` / `mock_body.py` scripts included in each service:

**Test the Brain against a mocked Body** (no CoppeliaSim connection
required on the Body side):

```sh
docker compose -f docker-compose.yml -f docker-compose.mock.yml up
```

**Test the Body against a mocked Brain** (drives CoppeliaSim without
waiting for real mission logic):

```sh
docker compose -f docker-compose.yml -f docker-compose.mockBrain.yml up
```

## Configuration

Environment variables (already set in `docker-compose.yml`, listed here
for reference):

| Variable | Used by | Purpose |
|---|---|---|
| `REDIS_HOST` | brain, body | Hostname of the Redis service (`agv_redis`) |
| `COPPELIA_HOST` | body | Hostname/IP where CoppeliaSim's `zmqRemoteApi` server is reachable (`host.docker.internal`) |
| `PYTHONPATH` | brain, body | Ensures the `modules/` package is importable |

The warehouse graph (named locations and their node IDs) is defined in
`src/body/docs/node_map_id.json` and should match the CoppeliaSim scene's
AprilTag placement.

## Known Limitations (Simulation Phase)

- The `agv_vision` (YOLO person-detection) container is present but
  disabled by default; safety stopping currently relies on the LiDAR
  proximity sensor.
- No structured logging system or real-time monitoring GUI is
  implemented yet; use `docker compose logs` to inspect service output.

## Team

Matteo Maloni, Nadia Muzyka, Andrea Iannotti — Master's Degree in
Computer Engineering, Università degli Studi dell'Aquila.
