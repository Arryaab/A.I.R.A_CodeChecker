class Inventory:
    def __init__(self):
        self.items = {}

    def add_item(self, item_name, quantity, price):
        if item_name in self.items:
            self.items[item_name]['quantity'] += quantity
            self.items[item_name]['price'] = price
        else:
            self.items[item_name] = {'quantity': quantity, 'price': price}

    def remove_item(self, item_name, quantity):
        if item_name not in self.items:
            raise KeyError(f"{item_name} not found in inventory")
        if self.items[item_name]['quantity'] < quantity:
            raise ValueError("Not enough items in inventory")
        self.items[item_name]['quantity'] -= quantity

    def get_quantity(self, item_name):
        return self.items.get(item_name, {}).get('quantity', 0)

    def get_total_value(self):
        return sum(item['quantity'] * item['price'] for item in self.items.values())
