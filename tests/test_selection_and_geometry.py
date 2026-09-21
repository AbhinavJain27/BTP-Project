import geopandas as gpd
from shapely.geometry import LineString, GeometryCollection

from river_networks.preprocessing.extract import _match_selection
from river_networks.preprocessing.standardize import validate_and_clean_geometry

def test_selection_method_is_authoritative():
    frame = gpd.GeoDataFrame({"MAIN_RIV": [1, 2], "HYRIV_ID": [10, 20], "HYBAS_ID": [100, 200]})
    mask, criteria = _match_selection(frame, {"method": "hyriv_ids", "hyriv_ids": [20]})
    assert mask.tolist() == [False, True]
    assert criteria == ["HYRIV_ID in [20]"]

def test_geometry_repair_drops_non_line_results():
    frame = gpd.GeoDataFrame(
        {"HYRIV_ID": [1, 2], "geometry": [LineString([(0, 0), (1, 1)]), GeometryCollection([])]},
        geometry="geometry",
        crs="EPSG:4326",
    )
    cleaned = validate_and_clean_geometry(frame)
    assert cleaned["HYRIV_ID"].tolist() == [1]
