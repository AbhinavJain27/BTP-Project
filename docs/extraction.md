# River Extraction & Topological Closure

This document describes how river networks are selected and extracted from the regional HydroRIVERS datasets, and how topological completeness is enforced.

---

## 1. Selection Methodology

In HydroRIVERS, reach records do not contain string river names. Instead, river networks are defined topologically using the `MAIN_RIV` field:

- **`MAIN_RIV`**: Identifies the `HYRIV_ID` of the most downstream reach (the terminal outlet) of a connected river basin.
- When an extraction specifies `selection.method: main_riv` with a target `main_riv_id`, the pipeline selects **every reach that flows into that terminal outlet**.
- **Basin-Wide Integrity**: This ensures that all tributaries, headwaters, and confluence points are preserved as a connected hydrological tree rather than isolating only the named main stem.

### Configured Rivers (`config/rivers.yaml`)
- **Amazon**: `MAIN_RIV = 60443230` (South America)
- **Ganges**: `MAIN_RIV = 41067217` (Asia) — encompasses the full Ganges-Brahmaputra-Meghna (GBM) delta system.
- **Godavari**: `MAIN_RIV = 41275841` (Asia)
- **Krishna**: `MAIN_RIV = 41297283` (Asia)
- **Nile**: `MAIN_RIV = 10047863` (Africa)
- **Yangtze**: `MAIN_RIV = 40613666` (Asia)

---

## 2. Topological Closure & Validation

In [`extract.py`](file:///d:/BTP-abhinav/river-networks-phase1-complete/src/river_networks/preprocessing/extract.py), before saving the extracted dataset, the code enforces strict topological closure:

```python
ids = set(selected["HYRIV_ID"].dropna().astype(int))
missing_down = sorted({
    int(value) for value in selected["NEXT_DOWN"].dropna().astype(int) 
    if value != 0 and value not in ids
})
if missing_down:
    raise ValueError(f"Extraction is incomplete: {len(missing_down)} NEXT_DOWN references point outside...")
```

### Validation Guarantees:
1. **No External Pointers**: Every reach's `NEXT_DOWN` must either be `0` (the basin outlet to the sea or sink) or point to another reach `HYRIV_ID` within the extracted set.
2. **No Dangling Reaches**: If any reach points outside the selection, the extraction fails immediately.
3. **No Duplicate Reaches**: Enforces that all `HYRIV_ID` values are unique.
4. **Hydrological Self-Containment**: Guarantees that the extracted dataset forms a complete, closed directed network suitable for graph construction and network science calculations.
