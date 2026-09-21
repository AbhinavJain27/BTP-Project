from collections.abc import Iterable
from ..graph.fields import HYDRORIVERS_FIELDS

def validate_reach_schema(columns:Iterable[str])->list[str]:
    available=set(columns)
    return [field for field in HYDRORIVERS_FIELDS if field not in available]
