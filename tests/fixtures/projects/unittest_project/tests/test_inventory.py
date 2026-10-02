import unittest
from inventory import Inventory

class TestInventory(unittest.TestCase):
    def setUp(self):
        self.inv = Inventory()

    def test_add_item(self):
        self.inv.add_item("apple", 10, 1.5)
        self.assertEqual(self.inv.get_quantity("apple"), 10)

    def test_remove_item(self):
        self.inv.add_item("apple", 10, 1.5)
        self.inv.remove_item("apple", 5)
        self.assertEqual(self.inv.get_quantity("apple"), 5)

    def test_remove_item_error(self):
        with self.assertRaises(KeyError):
            self.inv.remove_item("banana", 1)

    def test_remove_item_too_many(self):
        self.inv.add_item("apple", 10, 1.5)
        with self.assertRaises(ValueError):
            self.inv.remove_item("apple", 15)

    def test_get_total_value(self):
        self.inv.add_item("apple", 10, 1.5)
        self.inv.add_item("banana", 5, 2.0)
        self.assertEqual(self.inv.get_total_value(), 25.0)

if __name__ == '__main__':
    unittest.main()
