from dataclasses import dataclass
from typing import Any

@dataclass
class StandardizedReach:
    hyriv_id: int
    next_down: int | None
    main_riv: int | None
    hybas_id: int | None
    length_km: float | None
    dist_dn_km: float | None
    dist_up_km: float | None
    catch_skm: float | None
    upland_skm: float | None
    dis_av_cms: float | None
    endorheic: int | None
    ord_stra: int | None
    ord_clas: int | None
    ord_flow: int | None
    geometry: Any = None
