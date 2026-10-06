"""Generate a deterministic, fully synthetic patient dataset.

No real patient data is used. Names are drawn from a small pool, and every value comes from
a seeded RNG so the file is reproducible:

    python scripts/generate_sample_data.py > data/sample_patients.json
"""

from __future__ import annotations

import json
import random

FIRST = [
    "Aarav",
    "Meera",
    "Karthik",
    "Divya",
    "Rohan",
    "Ananya",
    "Vikram",
    "Priya",
    "Arjun",
    "Sneha",
    "Nikhil",
    "Lakshmi",
    "Suresh",
    "Kavya",
    "Imran",
    "Fatima",
    "David",
    "Maria",
    "Tomas",
    "Yuki",
]
LAST = [
    "Iyer",
    "Nair",
    "Reddy",
    "Sharma",
    "Menon",
    "Pillai",
    "Gupta",
    "Rao",
    "Khan",
    "Das",
    "Patel",
    "Joseph",
    "Kumar",
    "Bose",
    "Verma",
    "Shah",
]
DEPARTMENTS = {
    # department: (doctors, typical stay range, consultation range)
    "Cardiology": (["Dr. Ramesh", "Dr. Anjali"], (2, 12), (800, 1800)),
    "Neurology": (["Dr. Subramanian", "Dr. Kavitha"], (3, 15), (900, 2000)),
    "Orthopedics": (["Dr. Prakash", "Dr. Neha"], (2, 20), (700, 1500)),
    "Pediatrics": (["Dr. Meenakshi", "Dr. Farhan"], (1, 7), (500, 1100)),
    "Oncology": (["Dr. Venkat", "Dr. Ishita"], (5, 30), (1200, 2500)),
    "General Medicine": (["Dr. Rajan", "Dr. Sunita"], (1, 8), (400, 900)),
}


def build(count: int = 40, seed: int = 42) -> dict:
    rng = random.Random(seed)
    dept_names = list(DEPARTMENTS)
    patients = []
    for i in range(count):
        dept = dept_names[i % len(dept_names)] if i < len(dept_names) else rng.choice(dept_names)
        doctors, (lo, hi), (c_lo, c_hi) = DEPARTMENTS[dept]
        days = rng.randint(lo, hi)
        age = rng.randint(2, 12) if dept == "Pediatrics" else rng.randint(24, 86)
        patients.append(
            {
                "id": 201 + i,
                "name": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
                "age": age,
                "department": dept,
                "doctor": rng.choice(doctors),
                "status": rng.choices(["Admitted", "Discharged"], weights=[35, 65])[0],
                "daysAdmitted": days,
                "bill": {
                    "consultation": rng.randrange(c_lo, c_hi, 50),
                    "medicine": rng.randrange(200, 400 + days * 150, 25),
                    "lab": rng.randrange(150, 300 + days * 120, 25),
                },
            }
        )
    return {"data": {"patients": patients}}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
