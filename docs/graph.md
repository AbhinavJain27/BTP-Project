# Graph Construction & Network Science Metrics

Phase 1 constructs mathematical graph representations from HydroRIVERS reach topology and computes comprehensive network science metrics.

---

## 1. Graph Construction

### Topology Model
- **Edges**: Every HydroRIVERS reach becomes one directed edge in the graph. Direction follows `NEXT_DOWN`, flowing from upstream reaches toward downstream targets.
- **Vertices (Nodes)**:
  - `junction:HYRIV_ID`: The upstream connection point of that reach and the shared confluence point for any reaches flowing into it.
  - `outlet:HYRIV_ID`: Terminal boundary node created for reaches where `NEXT_DOWN = 0` (discharging into the ocean or an endorheic sink).
- **Node Taxonomy**:
  - **Headwater** (`in_degree = 0`, `out_degree = 1`): Source tips of river branches.
  - **Confluence / Junction** (`in_degree ≥ 2`, `out_degree = 1`): Meeting points where two or more tributaries merge.
  - **Downstream / Outlet** (`in_degree ≥ 1`, `out_degree = 0`): Terminal basin endpoints.
  - **Intermediate** (`in_degree = 1`, `out_degree = 1`): Topology-preserving single-channel pass-throughs.

### Dual Representation
1. **Directed Graph** (`directed.graphml`): Encodes hydrological flow direction (DAG). Edge attributes preserve all HydroRIVERS properties (`LENGTH_KM`, `CATCH_SKM`, `DIS_AV_CMS`, `ORD_STRA`, etc.).
2. **Undirected Graph** (`undirected.graphml`): Encodes physical network connectivity for structural metrics (e.g. undirected diameter, unweighted shortest paths).
3. **Columnar Nodes** (`nodes.parquet`): Precomputed vertex table (`node_id`, `reach_id`, `node_type`, `in_degree`, `out_degree`, `degree`, coordinates) for sub-second, zero-RAM dashboard loading.

---

## 2. Topological Validation Rules

Every constructed graph must pass strict sanity validations:
- **Simple Graph**: No self-loops (`self_loops == 0`) and no multi-edges.
- **Acyclic Flow (DAG)**: Verified via `graph.is_dag() == True`. Water only flows downstream; directed cycles are strictly invalid.
- **Connectivity**: Evaluates weakly connected components (a well-formed basin has one dominant giant component containing 100% of reaches) and strongly connected components (all components are size 1 in a DAG).

---

## 3. Network Science Metrics

Computed by [`compute_network_metrics()`](file:///d:/BTP-abhinav/river-networks-phase1-complete/src/river_networks/graph/metrics.py) and stored in `network_metrics.json`:

1. **Size & Density**:
   - `node_count` ($|V|$): Total topological vertices.
   - `edge_count` ($|E|$): Total directed reaches.
   - `density`: Ratio $|E| / (|V|(|V|-1))$, ranging from $10^{-6}$ to $10^{-5}$ (ultra-sparse dendritic trees).
2. **Degree Metrics**:
   - In-degree, out-degree, and total degree: min, max, mean, median, standard deviation, and full frequency distribution.
3. **Diameters & Path Lengths**:
   - **Directed Diameter**: Longest directed downstream path from any headwater to the outlet, in reach hops.
   - **Undirected Diameter**: Longest shortest path between any two vertices across the entire basin, computed in $O(V)$ time via two-sweep BFS.
   - **Average Path Length**: Mean path length for directed reachable pairs and undirected connected pairs.
   - **Shortest Paths to Outlet**: Downstream distance from every node to the nearest terminal outlet in reach hops.
4. **Centrality Measures**:
   - **Degree Centrality**: Normalized degree distribution.
   - **Betweenness Centrality**: Identifies topological flow bottlenecks where multiple sub-basins funnel into a single channel.
   - **PageRank Centrality**: Models downstream accumulation; nodes with the highest PageRank correspond to major trunk channels draining large tributary networks.
5. **Clustering Coefficient (Transitivity)**:
   - Global transitivity measuring closed triangles. Dendritic drainage trees have strictly **0 closed triangles** (clustering coefficient = 0.0000).
