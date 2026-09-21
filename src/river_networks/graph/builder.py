from pathlib import Path
from typing import Any

def _require_igraph():
    try:
        import igraph as ig
    except ImportError as exc:
        raise RuntimeError("igraph is required for graph construction. Install project dependencies before building a graph.") from exc
    return ig

def _records(processed_reaches):
    if hasattr(processed_reaches,"iterrows"):
        return processed_reaches
    import geopandas as gpd
    return gpd.read_parquet(processed_reaches)

def build_river_graph(processed_reaches):
    ig=_require_igraph()
    frame=_records(processed_reaches)
    required={"HYRIV_ID","NEXT_DOWN"}
    missing=required-set(frame.columns)
    if missing:
        raise ValueError(f"Processed reaches are missing required graph fields: {', '.join(sorted(missing))}")
    if frame["HYRIV_ID"].isna().any():
        raise ValueError("Processed reaches contain missing HYRIV_ID values.")
    if frame["HYRIV_ID"].duplicated().any():
        raise ValueError("Processed reaches contain duplicate HYRIV_ID values.")
    frame=frame.copy()
    frame["HYRIV_ID"]=frame["HYRIV_ID"].astype(int)
    frame["NEXT_DOWN"]=frame["NEXT_DOWN"].fillna(0).astype(int)
    ids=set(frame["HYRIV_ID"])
    missing_down=sorted({value for value in frame["NEXT_DOWN"] if value!=0 and value not in ids})
    if missing_down:
        raise ValueError(f"Processed reaches contain missing NEXT_DOWN references. First missing IDs: {missing_down[:10]}")
    self_loops=sorted(set(frame.loc[frame["HYRIV_ID"]==frame["NEXT_DOWN"],"HYRIV_ID"]))
    if self_loops:
        raise ValueError(f"Processed reaches contain self-loops: {self_loops[:10]}")
    frame=frame.copy()
    frame["HYRIV_ID"]=frame["HYRIV_ID"].astype(int)
    frame["NEXT_DOWN"]=frame["NEXT_DOWN"].fillna(0).astype(int)
    ids=set(frame["HYRIV_ID"])
    missing_down=sorted({value for value in frame["NEXT_DOWN"] if value!=0 and value not in ids})
    if missing_down:
        raise ValueError(f"Processed reaches contain missing NEXT_DOWN references. First missing IDs: {missing_down[:10]}")
    self_loops=sorted(set(frame.loc[frame["HYRIV_ID"]==frame["NEXT_DOWN"],"HYRIV_ID"]))
    if self_loops:
        raise ValueError(f"Processed reaches contain self-loops: {self_loops[:10]}")

    hyriv_ids=frame["HYRIV_ID"].to_numpy()
    next_down=frame["NEXT_DOWN"].to_numpy()
    sources=[f"junction:{h}" for h in hyriv_ids]
    targets=[f"junction:{n}" if n!=0 else f"outlet:{h}" for h,n in zip(hyriv_ids,next_down)]
    node_ids=sorted(set(sources)|set(targets))
    index={node_id:i for i,node_id in enumerate(node_ids)}
    graph=ig.Graph(n=len(node_ids),directed=True)
    graph.vs["node_id"]=node_ids
    graph.add_edges([(index[s],index[t]) for s,t in zip(sources,targets)])

    edge_attrs={"edge_id":[f"reach:{h}" for h in hyriv_ids],"HYRIV_ID":[int(h) for h in hyriv_ids]}
    geometry_wkt=None
    for column in frame.columns:
        if column=="HYRIV_ID":
            continue
        if column=="geometry":
            geometry_wkt=frame[column].apply(lambda g: g.wkt if g is not None else None).tolist()
            edge_attrs[column]=geometry_wkt
            continue
        series=frame[column]
        values=[None if (v is None or (isinstance(v,float) and v!=v)) else (v.item() if hasattr(v,"item") else v) for v in series.tolist()]
        edge_attrs[column]=values
    for name,values in edge_attrs.items():
        graph.es[name]=values
    in_degree=graph.indegree()
    out_degree=graph.outdegree()
    node_types=[]
    for i,node_id in enumerate(node_ids):
        if node_id.startswith("outlet:"):
            node_type="downstream/outlet"
        elif in_degree[i]==0:
            node_type="headwater"
        elif in_degree[i]>1:
            node_type="confluence/junction"
        else:
            node_type="intermediate/topology-preserving"
        node_types.append(node_type)
    graph.vs["node_type"]=node_types
    graph.vs["degree"]=[a+b for a,b in zip(in_degree,out_degree)]
    graph.vs["in_degree"]=in_degree
    graph.vs["out_degree"]=out_degree

    undirected=graph.as_undirected(combine_edges="first")

    node_wkt=[None] * graph.vcount()
    if "geometry" in frame.columns:
        for source,target,geom in zip(sources,targets,frame["geometry"].tolist()):
            if geom is None or geom.is_empty:
                continue
            try:
                parts = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
                if not parts:
                    continue
                start_coord = parts[0].coords[0]
                end_coord = parts[-1].coords[-1]
            except (TypeError, ValueError, AttributeError, IndexError):
                continue
            s_i=index[source]
            t_i=index[target]
            if node_wkt[s_i] is None:
                node_wkt[s_i]=start_coord
            if node_wkt[t_i] is None:
                node_wkt[t_i]=end_coord
    graph.vs["geometry"]=[
        None if coord is None else f"POINT ({coord[0]} {coord[1]})"
        for coord in node_wkt
    ]
    graph.vs["x"]=[None if coord is None else float(coord[0]) for coord in node_wkt]
    graph.vs["y"]=[None if coord is None else float(coord[1]) for coord in node_wkt]
    undirected.vs["geometry"]=list(graph.vs["geometry"])
    undirected.vs["x"]=list(graph.vs["x"])
    undirected.vs["y"]=list(graph.vs["y"])
    return graph,undirected

def validate_graph(graph)->dict[str,Any]:
    issues=[]
    warnings=[]
    if graph.ecount()==0 and graph.vcount()>0:
        issues.append("Graph has nodes but no edges")
    duplicate_ids=len(graph.es["HYRIV_ID"])!=len(set(graph.es["HYRIV_ID"])) if "HYRIV_ID" in graph.es.attributes() else False
    if duplicate_ids:
        issues.append("Graph contains duplicate edge HYRIV_ID values")
    self_loop_count=sum(graph.is_loop())
    if self_loop_count:
        issues.append(f"Graph contains {self_loop_count} self-loops")
    components=graph.as_undirected().components()
    if len(components)>1:
        warnings.append(f"Graph contains {len(components)} disconnected components")
    expected_edges=graph.ecount()
    if expected_edges<1:
        issues.append("Graph contains no edges")
    return {"valid":not issues,"issues":issues,"warnings":warnings,"node_count":graph.vcount(),"edge_count":graph.ecount(),"weak_component_count":len(components),"density":graph.density()}
