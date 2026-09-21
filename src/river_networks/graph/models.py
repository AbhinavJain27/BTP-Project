from dataclasses import dataclass,field
from typing import Any

@dataclass
class NodeRecord:
    node_id:str
    node_type:str
    attributes:dict[str,Any]=field(default_factory=dict)
    geometry:Any=None

@dataclass
class EdgeRecord:
    edge_id:str
    source:str
    target:str
    attributes:dict[str,Any]=field(default_factory=dict)
    geometry:Any=None
