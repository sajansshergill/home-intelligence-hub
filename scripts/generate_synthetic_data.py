"""
generate_synthetic_data.py
--------------------------
Generates synthetic home health care coordination data using Faker.
All data is fictional. No real PHI is used.

Outputs (to data/synthetic/):
  - patients.csv
  - clinicians.csv
  - payors.csv
  - referrals.csv
  - payor_authorizations.csv
  - visits.csv

Usage:
    python scripts/generate_synthetic_data.py
    python scripts/generate_synthetic_data.py --records 5000 --seed 99
"""

import argparse
import csv
import os
import random
from datetime import datetime, timedelta
from pathlib import Path
from faker import Faker

fake = Faker()

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "data" / "synthetic"

REFERRAL_STATUSES   = ["pending", "accepted", "rejected", "cancelled"]
REFERRAL_STATUS_W   = [0.10, 0.72, 0.10, 0.08]

AUTH_STATUSES        = ["submitted", "approved", "denied", "pending_info"]
AUTH_STATUS_W        = [0.08, 0.74, 0.10, 0.08]

VISIT_STATUSES       = ["scheduled", "completed", "missed", "cancelled"]
VISIT_STATUS_W       = [0.10, 0.76, 0.08, 0.06]

SPECIALTIES          = ["Registered Nurse", "Physical Therapist",
                        "Occupational Therapist", "Speech Therapist",
                        "Home Health Aide", "Social Worker"]

PAYOR_NAMES          = [
    "BlueCross BlueShield", "Aetna", "UnitedHealthcare",
    "Cigna", "Humana", "Medicaid - NJ", "Medicare FFS",
    "Wellcare", "Molina Healthcare", "AmeriHealth"
]

# Payor-level avg authorization lag in business days (some are slow)
PAYOR_LAG_PROFILE = {
    "BlueCross BlueShield": (3, 2),
    "Aetna":                (4, 2),
    "UnitedHealthcare":     (5, 3),
    "Cigna":                (4, 2),
    "Humana":               (6, 3),
    "Medicaid - NJ":        (10, 4),
    "Medicare FFS":         (2, 1),
    "Wellcare":             (8, 4),
    "Molina Healthcare":    (9, 5),
    "AmeriHealth":          (5, 2),
}

DIAGNOSIS_CODES = [
    ("Z87.39", "Personal history of other musculoskeletal disorders"),
    ("I50.9",  "Heart failure, unspecified"),
    ("J44.1",  "COPD with acute exacerbation"),
    ("N18.3",  "Chronic kidney disease, stage 3"),
    ("E11.9",  "Type 2 diabetes without complications"),
    ("M54.5",  "Low back pain"),
    ("G30.9",  "Alzheimer's disease, unspecified"),
    ("I63.9",  "Cerebral infarction, unspecified"),
    ("F32.9",  "Major depressive disorder, single episode"),
    ("Z96.641","Presence of right artificial hip joint"),
]


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def rand_date(start: datetime, end: datetime) -> datetime:
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))


def add_business_days(start: datetime, days: int) -> datetime:
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:  # Mon–Fri
            added += 1
    return current


def weighted_choice(choices, weights):
    return random.choices(choices, weights=weights, k=1)[0]


def save_csv(rows: list[dict], filename: str):
    path = OUTPUT_DIR / filename
    if not rows:
        return
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"  {filename:40s} {len(rows):>6} rows -> {path}")


# ──────────────────────────────────────────────
# Generators
# ──────────────────────────────────────────────

def gen_patients(n: int) -> list[dict]:
    rows = []
    for i in range(1, n + 1):
        dob = fake.date_of_birth(minimum_age=45, maximum_age=92)
        diagnosis_code, diagnosis_desc = random.choice(DIAGNOSIS_CODES)
        rows.append({
            "patient_id":        f"PAT-{i:06d}",
            # NOTE: In production, name/DOB/address are PHI — masked via Snowflake DDM
            "patient_token":     fake.uuid4(),           # tokenized identifier for mart layer
            "gender":            random.choice(["M", "F", "Other"]),
            "date_of_birth":     dob.isoformat(),        # PHI — masked in prod
            "zip_code":          fake.zipcode(),
            "state":             fake.state_abbr(),
            "primary_diagnosis_code":  diagnosis_code,
            "primary_diagnosis_desc":  diagnosis_desc,
            "insurance_member_id":     fake.bothify("??######"),  # PHI — masked in prod
            "created_at":        fake.date_time_this_decade().isoformat(),
        })
    return rows


def gen_clinicians(n: int) -> list[dict]:
    rows = []
    for i in range(1, n + 1):
        specialty = random.choice(SPECIALTIES)
        rows.append({
            "clinician_id":           f"CLIN-{i:04d}",
            "first_name":             fake.first_name(),
            "last_name":              fake.last_name(),
            "specialty":              specialty,
            "license_number":         fake.bothify("LIC-####??"),
            "weekly_capacity_visits": random.randint(18, 35),
            "zip_code":               fake.zipcode(),
            "state":                  fake.state_abbr(),
            "active":                 random.choices([True, False], weights=[0.92, 0.08])[0],
            "hire_date":              fake.date_between(start_date="-8y", end_date="-6m").isoformat(),
            "created_at":             fake.date_time_this_decade().isoformat(),
        })
    return rows


def gen_payors() -> list[dict]:
    rows = []
    for i, name in enumerate(PAYOR_NAMES, 1):
        lag_mean, lag_std = PAYOR_LAG_PROFILE[name]
        rows.append({
            "payor_id":            f"PAY-{i:03d}",
            "payor_name":          name,
            "payor_type":          "Government" if name in ("Medicaid - NJ", "Medicare FFS") else "Commercial",
            "avg_auth_lag_days":   lag_mean,
            "requires_prior_auth": random.choice([True, False]),
            "portal_url":          fake.url(),
            "created_at":          fake.date_time_this_decade().isoformat(),
        })
    return rows


def gen_referrals(n: int, patient_ids: list, payor_ids: list) -> list[dict]:
    start = datetime(2023, 1, 1)
    end   = datetime(2025, 3, 31)
    rows  = []
    for i in range(1, n + 1):
        ref_date = rand_date(start, end)
        status   = weighted_choice(REFERRAL_STATUSES, REFERRAL_STATUS_W)

        accepted_date = None
        if status == "accepted":
            accepted_date = (ref_date + timedelta(hours=random.randint(1, 72))).isoformat()

        rows.append({
            "referral_id":          f"REF-{i:07d}",
            "patient_id":           random.choice(patient_ids),
            "payor_id":             random.choice(payor_ids),
            "referring_provider":   fake.name(),
            "referring_facility":   fake.company() + " Hospital",
            "referral_date":        ref_date.isoformat(),
            "accepted_date":        accepted_date,
            "status":               status,
            "urgency":              weighted_choice(["routine", "urgent", "emergent"], [0.65, 0.28, 0.07]),
            "service_type":         random.choice(["Skilled Nursing", "Physical Therapy",
                                                    "Occupational Therapy", "Speech Therapy",
                                                    "Home Health Aide", "MSW"]),
            "notes":                fake.sentence(nb_words=12) if random.random() > 0.6 else None,
            "created_at":           ref_date.isoformat(),
        })
    return rows


def gen_authorizations(referrals: list, payors: list) -> list[dict]:
    payor_lag = {p["payor_id"]: PAYOR_LAG_PROFILE[p["payor_name"]] for p in payors}
    rows = []
    auth_counter = 1

    for ref in referrals:
        if ref["status"] not in ("accepted",):
            continue
        if random.random() < 0.05:   # ~5% accepted referrals skip auth (e.g. Medicare waiver)
            continue

        payor_id  = ref["payor_id"]
        lag_mean, lag_std = payor_lag.get(payor_id, (5, 2))
        ref_date  = datetime.fromisoformat(ref["referral_date"])
        submitted = ref_date + timedelta(hours=random.randint(2, 48))
        lag_days  = max(1, int(random.gauss(lag_mean, lag_std)))
        status    = weighted_choice(AUTH_STATUSES, AUTH_STATUS_W)
        units_requested = random.randint(4, 24)

        approved_date = None
        if status == "approved":
            approved_date = add_business_days(submitted, lag_days).isoformat()

        rows.append({
            "auth_id":           f"AUTH-{auth_counter:07d}",
            "referral_id":       ref["referral_id"],
            "payor_id":          payor_id,
            "submitted_date":    submitted.isoformat(),
            "approved_date":     approved_date,
            "denied_date":       (add_business_days(submitted, lag_days).isoformat()
                                  if status == "denied" else None),
            "status":            status,
            "auth_lag_days":     lag_days if status == "approved" else None,
            "units_requested":   units_requested,
            "units_approved":    random.randint(1, units_requested) if status == "approved" else None,
            "denial_reason":     (random.choice([
                                    "Not medically necessary",
                                    "Incomplete documentation",
                                    "Out of network",
                                    "Benefit limit reached"
                                  ]) if status == "denied" else None),
            "created_at":        submitted.isoformat(),
        })
        auth_counter += 1
    return rows


def gen_visits(referrals: list, clinician_ids: list) -> list[dict]:
    rows = []
    visit_counter = 1

    for ref in referrals:
        if ref["status"] != "accepted":
            continue

        ref_date = datetime.fromisoformat(ref["referral_date"])
        num_visits = random.randint(1, 12)

        for v in range(num_visits):
            scheduled = ref_date + timedelta(days=random.randint(3 + v * 3, 7 + v * 4))
            status    = weighted_choice(VISIT_STATUSES, VISIT_STATUS_W)

            completed_date = None
            duration_min   = None
            if status == "completed":
                completed_date = (scheduled + timedelta(
                    hours=random.uniform(-1, 2)
                )).isoformat()
                duration_min = random.randint(30, 90)

            rows.append({
                "visit_id":         f"VIS-{visit_counter:08d}",
                "referral_id":      ref["referral_id"],
                "patient_id":       ref["patient_id"],
                "clinician_id":     random.choice(clinician_ids),
                "scheduled_date":   scheduled.isoformat(),
                "completed_date":   completed_date,
                "status":           status,
                "visit_number":     v + 1,
                "service_type":     ref["service_type"],
                "duration_minutes": duration_min,
                "missed_reason":    (random.choice([
                                        "Patient unavailable",
                                        "Clinician no-show",
                                        "Weather",
                                        "Patient hospitalized"
                                      ]) if status == "missed" else None),
                "created_at":       scheduled.isoformat(),
            })
            visit_counter += 1

    return rows


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main(n_patients: int, n_clinicians: int, n_referrals: int, seed: int):
    random.seed(seed)
    Faker.seed(seed)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("\nHome Care Intelligence Hub - Synthetic Data Generator")
    print(f"   seed={seed} | patients={n_patients} | clinicians={n_clinicians} | referrals={n_referrals}\n")

    patients   = gen_patients(n_patients)
    clinicians = gen_clinicians(n_clinicians)
    payors     = gen_payors()

    patient_ids   = [p["patient_id"]   for p in patients]
    clinician_ids = [c["clinician_id"] for c in clinicians]
    payor_ids     = [p["payor_id"]     for p in payors]

    referrals      = gen_referrals(n_referrals, patient_ids, payor_ids)
    authorizations = gen_authorizations(referrals, payors)
    visits         = gen_visits(referrals, clinician_ids)

    save_csv(patients,       "patients.csv")
    save_csv(clinicians,     "clinicians.csv")
    save_csv(payors,         "payors.csv")
    save_csv(referrals,      "referrals.csv")
    save_csv(authorizations, "payor_authorizations.csv")
    save_csv(visits,         "visits.csv")

    print(f"\nDone. {len(referrals)} referrals -> "
          f"{len(authorizations)} authorizations -> "
          f"{len(visits)} visits\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic home health data")
    parser.add_argument("--patients",   type=int, default=2000,  help="Number of patients")
    parser.add_argument("--clinicians", type=int, default=80,    help="Number of clinicians")
    parser.add_argument("--referrals",  type=int, default=5000,  help="Number of referrals")
    parser.add_argument("--seed",       type=int, default=42,    help="Random seed")
    args = parser.parse_args()

    main(args.patients, args.clinicians, args.referrals, args.seed)