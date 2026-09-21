import json
from pathlib import Path
from typing import Any

def write_metadata(path:Path,data:dict[str,Any])->str:
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,default=str),encoding="utf-8")
    return str(path)
