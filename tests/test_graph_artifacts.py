import pytest

ig = pytest.importorskip("igraph")

from river_networks.storage.graph import load_graph_artifact, save_graph_artifact

def test_graphml_round_trip_preserves_integer_ids_and_path_strings(tmp_path):
    graph = ig.Graph(n=2, directed=True)
    graph.vs["node_id"] = ["junction:1", "outlet:1"]
    graph.vs["in_degree"] = [0, 1]
    graph.vs["out_degree"] = [1, 0]
    graph.vs["degree"] = [1, 1]
    graph.add_edge(0, 1)
    graph.es["HYRIV_ID"] = [40631851]
    graph.es["NEXT_DOWN"] = [0]
    graph.es["MAIN_RIV"] = [40631851]
    graph.es["HYBAS_ID"] = [41000001]
    graph.es["ENDORHEIC"] = [0]
    graph.es["ORD_STRA"] = [1]
    graph.es["ORD_CLAS"] = [1]
    graph.es["ORD_FLOW"] = [5]
    graph.es["LENGTH_KM"] = [12.5]
    graph.es["edge_id"] = ["reach:40631851"]
    graph.es["geometry"] = ["LINESTRING (77 25, 77.1 25.1)"]

    directory = tmp_path / "river_graph"
    save_graph_artifact(graph, graph.as_undirected(combine_edges="first"), directory, {"cache_key": "test"})
    directed, undirected, metadata = load_graph_artifact(directory)

    assert isinstance(directed.es["HYRIV_ID"][0], int)
    assert directed.es["HYRIV_ID"][0] == 40631851
    assert directed.es["NEXT_DOWN"][0] == 0
    assert "HYRIV_ID" in undirected.es.attributes()
    assert undirected.es["HYRIV_ID"][0] == 40631851
    assert metadata["cache_key"] == "test"

def test_build_river_graph_handles_multilinestring_reach_geometry():
    import geopandas as gpd
    from shapely.geometry import MultiLineString
    from river_networks.graph.builder import build_river_graph

    frame = gpd.GeoDataFrame(
        {
            "HYRIV_ID": [101, 102],
            "NEXT_DOWN": [102, 0],
            "LENGTH_KM": [1.0, 2.0],
            "geometry": [
                MultiLineString([[(10, 20), (11, 21)], [(11, 21), (12, 22)]]),
                MultiLineString([[(12, 22), (13, 23)]])
            ],
        },
        geometry="geometry",
        crs="EPSG:4326",
    )

    directed, undirected = build_river_graph(frame)

    source_idx = directed.vs.find(node_id="junction:101").index
    downstream_idx = directed.vs.find(node_id="junction:102").index
    outlet_idx = directed.vs.find(node_id="outlet:102").index
    assert directed.vs[source_idx]["geometry"] == "POINT (10.0 20.0)"
    assert directed.vs[downstream_idx]["geometry"] == "POINT (12.0 22.0)"
    assert directed.vs[outlet_idx]["geometry"] == "POINT (13.0 23.0)"
    assert "HYRIV_ID" in undirected.es.attributes()
    assert undirected.ecount() == 2
