import numpy as np

RANDOM_NUMBER_GENERATOR = np.random.default_rng()


def random_float(lower_bound: float = 0.0, upper_bound: float = 1.0) -> float:
    return (upper_bound - lower_bound) * RANDOM_NUMBER_GENERATOR.random() + lower_bound


def random_int(lower_bound: int = 0, upper_bound: int = 100) -> int:
    return int(random_float(lower_bound, upper_bound))
