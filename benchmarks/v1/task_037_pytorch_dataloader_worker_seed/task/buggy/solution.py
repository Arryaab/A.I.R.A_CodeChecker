def generate_worker_seed(base_seed: int, worker_id: int) -> int:
    # BUG: returns base_seed ignoring worker_id, leading to duplicate samples across workers
    return base_seed
