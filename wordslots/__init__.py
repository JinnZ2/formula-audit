"""wordslots -- place table, claim records, slot check. Branch 4. Co-authored."""
from .check import EVIDENTIAL, RECORD_FIELDS, check_all, check_claim, read_table

__all__ = ["EVIDENTIAL", "RECORD_FIELDS", "check_claim", "check_all", "read_table"]
