# Data Model

This document defines the schema, data types, and entity relationships across the HydroRIVERS extraction and graph pipeline.

---

## 1. Reach Schema (`extracted_network.parquet`)

The extracted reach dataset is stored in GeoParquet format. It contains 15 standardized attributes:

| Field Name | Type | Description |
|---|---|---|
| `HYRIV_ID` | `Int64` | Unique reach identifier in HydroRIVERS. |
| `NEXT_DOWN` | `Int64` | `HYRIV_ID` of the next downstream reach (`0` for basin outlets). |
| `MAIN_RIV` | `Int64` | `HYRIV_ID` of the terminal outlet reach of the connected basin. |
| `HYBAS_ID` | `Int64` | Level-12 sub-basin identifier (`HYBAS_L12` in source GDB). |
| `LENGTH_KM` | `Float64` | Reach length in kilometers. |
| `DIST_DN_KM` | `Float64` | Distance along the river network to the final outlet in km. |
| `DIST_UP_KM` | `Float64` | Distance along the river network to the farthest headwater in km. |
| `CATCH_SKM` | `Float64` | Local sub-catchment area draining directly into this reach in $\text{km}^2$. |
| `UPLAND_SKM` | `Float64` | Total cumulative upstream catchment area in $\text{km}^2$. |
| `DIS_AV_CMS` | `Float64` | Long-term naturalized mean annual discharge in $\text{m}^3/\text{s}$. |
| `ENDORHEIC` | `Int64` | `1` if the reach drains into an inland sink/lake; `0` if it drains to the ocean. |
| `ORD_STRA` | `Int64` | Strahler stream order (1 = headwater, increases when equal orders meet). |
| `ORD_CLAS` | `Int64` | Stream order classification. |
| `ORD_FLOW` | `Int64` | Flow order reflecting downstream hierarchical progression. |
| `geometry` | `Geometry` | LineString or MultiLineString geometry in WGS 84 (EPSG:4326). |

---

## 2. Graph Node Schema (`nodes.parquet`)

Precomputed node table used by the Node Explorer:

| Field Name | Type | Description |
|---|---|---|
| `node_id` | `String` | Unique node string (e.g. `junction:41067217` or `outlet:41067217`). |
| `reach_id` | `String` | Source reach `HYRIV_ID` associated with this node. |
| `node_type` | `Category` | Topological role: `headwater`, `confluence/junction`, `downstream/outlet`, or `intermediate/topology-preserving`. |
| `in_degree` | `Int16` | Number of upstream tributary reaches entering this node. |
| `out_degree` | `Int16` | Number of downstream reaches leaving this node (`0` for outlets, `1` for flow channels). |
| `degree` | `Int16` | Total incident reaches (`in_degree + out_degree`). |
| `x` | `Float32` | Longitude in degrees (WGS 84). |
| `y` | `Float32` | Latitude in degrees (WGS 84). |

---

## 3. Network Metrics Schema (`network_metrics.json`)

JSON document storing precomputed network science metrics:

- `node_count` / `edge_count`: Integers representing $|V|$ and $|E|$.
- `density`: Float representing graph sparsity.
- `self_loops`: Integer count of self-loops (0 in valid networks).
- `diameter`: Object with `directed` and `undirected` hop distances.
- `average_path_length`: Object with `directed` and `undirected` mean distances.
- `in_degree`, `out_degree`, `degree`: Objects containing `min`, `max`, `mean`, `median`, `std`, and `counts` distribution dictionary.
- `connected_components`: Weak/strong component counts, largest component size, percentage, and `is_dag` boolean.
- `clustering_coefficient`: Object containing `global_transitivity` (0.0 for trees).
- `shortest_paths_to_outlet`: Mean, min, max, median hops, and histogram distribution.
- `centrality_measures`: Objects for `degree_centrality`, `betweenness_centrality`, and `pagerank_centrality` with max, mean, top node, and binned histograms.
