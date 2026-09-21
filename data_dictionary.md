# River Networks Data Dictionary

| Field | Meaning |
|---|---|
| `HYRIV_ID` | Unique HydroRIVERS reach identifier. |
| `NEXT_DOWN` | Next downstream `HYRIV_ID`; `0` is terminal. |
| `MAIN_RIV` | Most-downstream reach for the connected river basin. |
| `HYBAS_ID` | Internal name for official HydroRIVERS `HYBAS_L12`. |
| `LENGTH_KM`, `DIST_DN_KM`, `DIST_UP_KM` | Reach length and network distances in kilometres. |
| `CATCH_SKM`, `UPLAND_SKM` | Direct catchment and connected upstream area in square kilometres. |
| `DIS_AV_CMS` | Long-term average discharge in cubic metres per second. |
| `ENDORHEIC` | Inland-basin indicator: `0` non-endorheic, `1` endorheic. |
| `ORD_STRA`, `ORD_CLAS`, `ORD_FLOW` | Strahler, classical, and flow-based river-order attributes. |
| `geometry` | Reach geometry with source CRS preserved. |

Processed regional and extracted outputs use GeoParquet. Raw HydroRIVERS File Geodatabases are external and excluded from Git.
