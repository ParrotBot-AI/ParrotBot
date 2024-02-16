import datetime
import json
from enum import Enum

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()  # Convert datetime objects to ISO format strings
        elif isinstance(obj, Enum):
            return obj.value  # Convert enum instances to their value
        return super().default(obj)  # Fallback for other types