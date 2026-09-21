from dataclasses import dataclass
from pathlib import Path
from ..config import resolve_config

@dataclass(frozen=True)
class RiverPaths:
    river_root:Path
    raw:Path
    regional_source:Path
    regional_processed:Path
    processed:Path
    graphs:Path
    analysis:Path
    exports:Path
    metadata:Path

    @classmethod
    def for_river(cls,river_id:str)->"RiverPaths":
        paths=resolve_config(river_id)["paths"]
        return cls(*(Path(paths[key]) for key in ("river_root","raw","regional_source","regional_processed","processed","graphs","analysis","exports","metadata")))
