class GenericEnvelope:
    def __init__(self, item_cls):
        self.item_cls = item_cls

    def parse(self, payload: dict):
        # BUG: doesn't check if payload['items'] matches item_cls
        items = payload.get("items", [])
        return {"count": len(items), "items": items}
