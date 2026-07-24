# Body Documentation

## `node_map_id.json`

`node_map_id.json` defines the correspondence between the named locations
in the warehouse navigation graph and the numeric IDs assigned to their
AprilTags in the CoppeliaSim scene.

The file is consumed by the Body service. The AprilTag sensor loads it as a
mapping from node name to tag ID and creates the reverse mapping at runtime,
from tag ID to node name. The Redis interface also publishes the mapping in
`body_memory.node_id` so that the Brain service can use the same node
identifiers.

## File format

The file contains one JSON object:

```json
{
  "<node_name>": <april_tag_id>
}
```

| Field | Type | Description |
|---|---|---|
| Object key | string | Name of a node in the warehouse graph. |
| Object value | integer | Numeric ID of the AprilTag placed at that node. |

Node names are application-level labels used by the navigation logic. Tag
IDs are the values detected by the AprilTag sensor and must match the IDs
configured in the simulation scene.

## Current mapping

| Node name | AprilTag ID |
|---|---:|
| `ER` | 0 |
| `I7` | 1 |
| `I6` | 2 |
| `I3` | 3 |
| `I4` | 4 |
| `I5` | 5 |
| `I1` | 6 |
| `I2` | 7 |
| `E1` | 8 |
| `E2` | 9 |
| `E3` | 10 |
| `E4` | 11 |
| `EC` | 12 |

The current map contains 13 nodes, with IDs ranging from `0` to `12`.

## Maintenance rules

When adding or changing a node:

1. Update the node name and its numeric AprilTag ID in this file.
2. Update the corresponding AprilTag placement or configuration in the
   CoppeliaSim scene.
3. Keep every node name unique and every AprilTag ID unique. Duplicate IDs
   make the reverse mapping ambiguous.
4. Keep the JSON values as numbers, not quoted strings. For example, use
   `"E1": 8`, not `"E1": "8"`.
5. Update the table in this document so that it remains consistent with the
   configuration.

The mapping is loaded when the Body service starts. Restart the Body after
editing the file so that both the sensor and Redis state use the new values.

## Related components

- `../modules/sensors/apriltag_sensor.py` loads the mapping and resolves
  detected tag IDs to node names.
- `../modules/connection/redis_interface.py` publishes the mapping in
  `body_memory` during Body initialization.
- `../../../docs/GRAFO_STRUTTURA_PROGETTO.mmd` documents the project graph
  structure.