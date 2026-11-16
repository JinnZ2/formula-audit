"""numcheck -- data points and intersections. Branch 2b. Co-authored."""
import json
from decimal import Decimal

from .check import check_all, check_intersection, check_point
from .interval import Interval, IntervalVoid


def read_json(text):
    """JSON with every number read exactly as written (0.1 is one tenth)."""
    return json.loads(text, parse_float=Decimal)


__all__ = ["Interval", "IntervalVoid", "check_point", "check_intersection", "check_all",
           "read_json"]
