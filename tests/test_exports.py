import unittest
from pathlib import Path
import geopandas as gpd
from shapely.geometry import LineString

from river_networks.storage.exports import export_river_data, SUPPORTED_EXPORT_FORMATS
from river_networks.storage.paths import RiverPaths

class TestExports(unittest.TestCase):
    def test_supported_formats(self):
        self.assertIn("csv", SUPPORTED_EXPORT_FORMATS)
        self.assertIn("parquet", SUPPORTED_EXPORT_FORMATS)
        self.assertIn("geojson", SUPPORTED_EXPORT_FORMATS)

    def test_export_validation_on_missing_river(self):
        with self.assertRaises(Exception):
            export_river_data("non_existent_river", output_format="csv")

if __name__ == "__main__":
    unittest.main()
