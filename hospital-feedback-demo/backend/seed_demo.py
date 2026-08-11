"""Seeds the demo database with sample feedback so the dashboard has
meaningful data on first launch.

Usage:  py -3 seed_demo.py
"""
import sys

sys.path.insert(0, ".")

import database


def main():
    database.init_db()
    samples = [
        # visit_id, department, rating, sentiment, tags, comment
        ("VIS-2026-101", "OPD", 5, 0.85, ["STAFF_COURTESY", "QUALITY_OF_CARE"],
         "The doctor was excellent and very polite. Great attention."),
        ("VIS-2026-102", "EMERGENCY", 2, -0.6, ["LONG_WAIT"],
         "Waited over 3 hours in the emergency room for triage."),
        ("VIS-2026-103", "PHARMACY", 3, -0.15, ["DRUG_AVAILABILITY"],
         "Pharmacy staff were friendly but some drugs were out of stock."),
        ("VIS-2026-104", "BILLING", 4, 0.5, [],
         "Billing was quick and the staff explained everything clearly."),
        ("VIS-2026-105", "WARDS", 4, 0.6, ["QUALITY_OF_CARE"],
         "The nurses on the ward were attentive and caring."),
        ("VIS-2026-106", "EMERGENCY", 1, -0.9, ["LONG_WAIT", "DIRTY_FACILITY"],
         "The emergency room was dirty and we waited 4 hours."),
    ]
    for visit_id, dept, rating, sentiment, tags, comment in samples:
        database.insert_feedback({
            "visit_id": visit_id,
            "department_id": dept,
            "channel": "NURSE_ASSISTED",
            "patient_phone_hash": None,
            "overall_rating": rating,
            "sentiment_score": sentiment,
            "category_tags": tags,
            "raw_comment": comment,
            "summary": comment,
            "is_anonymous": False,
        })
    print(f"Seeded {len(samples)} sample feedback records (2 escalation alerts).")


if __name__ == "__main__":
    main()
