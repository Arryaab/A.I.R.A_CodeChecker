import hashlib

class BloomFilter:
    def __init__(self, size: int = 256, hash_count: int = 4):
        self.size = size
        self.hash_count = hash_count
        self.bit_array = [0] * size

    def _get_hashes(self, item: str):
        # BUG: Generates dependent hashes by simple linear addition
        base_h = int(hashlib.md5(item.encode()).hexdigest(), 16)
        return [(base_h + i) % self.size for i in range(self.hash_count)]

    def add(self, item: str) -> None:
        for idx in self._get_hashes(item):
            self.bit_array[idx] = 1

    def contains(self, item: str) -> bool:
        return all(self.bit_array[idx] == 1 for idx in self._get_hashes(item))
