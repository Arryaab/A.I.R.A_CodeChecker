class SecurityError(Exception):
    pass

class UserProfile:
    def __init__(self, name: str):
        self.name = name

ALLOWED_TYPES = {"UserProfile": UserProfile}

def instantiate_custom_type(type_name: str, kwargs: dict):
    # BUG: Directly accesses globals() allowing instantiation of arbitrary classes
    if type_name in globals():
        cls = globals()[type_name]
        return cls(**kwargs)
    raise ValueError(f"Unknown type: {type_name}")
