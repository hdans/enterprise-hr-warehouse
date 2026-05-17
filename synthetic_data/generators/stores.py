from __future__ import annotations

import numpy as np
import pandas as pd


def generate_stores(n_stores: int) -> pd.DataFrame:
    city_region_weight = [
        ("Jakarta Selatan", "Jabodetabek", 0.20),
        ("Jakarta Pusat", "Jabodetabek", 0.08),
        ("Jakarta Barat", "Jabodetabek", 0.07),
        ("Jakarta Utara", "Jabodetabek", 0.06),
        ("Jakarta Timur", "Jabodetabek", 0.06),
        ("Tangerang", "Jabodetabek", 0.05),
        ("Bekasi", "Jabodetabek", 0.04),
        ("Bogor", "Jabodetabek", 0.03),
        ("Bandung", "Jawa Barat", 0.06),
        ("Cimahi", "Jawa Barat", 0.02),
        ("Surabaya", "Jawa Timur", 0.06),
        ("Malang", "Jawa Timur", 0.02),
        ("Yogyakarta", "Jawa Tengah", 0.03),
        ("Semarang", "Jawa Tengah", 0.02),
        ("Bali", "Bali", 0.05),
        ("Medan", "Sumatera", 0.04),
        ("Palembang", "Sumatera", 0.02),
        ("Makassar", "Sulawesi", 0.03),
        ("Balikpapan", "Kalimantan", 0.02),
        ("Pontianak", "Kalimantan", 0.01),
        ("Pekanbaru", "Sumatera", 0.01),
        ("Manado", "Sulawesi", 0.01),
    ]
    cities, regions, weights = zip(*city_region_weight)
    w = np.array(weights, dtype=float)
    w /= w.sum()

    rows = []
    for i in range(1, n_stores + 1):
        idx = int(np.random.choice(len(cities), p=w))
        city = cities[idx]
        region = regions[idx]
        size = str(np.random.choice(["Small", "Medium", "Large"], p=[0.38, 0.42, 0.20]))
        rows.append(
            {
                "outlet_code": f"S{i:03d}",
                "outlet_name": f"Kopi Kenangan {city} {i:03d}",
                "city": city,
                "region": region,
                "size_label": size,
            }
        )

    return pd.DataFrame(rows)
