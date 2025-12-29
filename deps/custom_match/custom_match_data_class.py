"""
Data classes for custom match data access
"""
from dataclasses import dataclass


@dataclass
class MapSuggestion:
    """Data class for the map suggestion table"""

    map_name: str
    count: int

    @staticmethod
    def from_db_row(row):
        """Create a MapSuggestion object from a database row"""
        return MapSuggestion(
            map_name=row[0],
            count=row[1],
        )
