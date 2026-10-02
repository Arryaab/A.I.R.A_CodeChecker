from decimal import Decimal
from datetime import datetime

def custom_serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    # BUG: Decimal raises TypeError
    return str(obj)
