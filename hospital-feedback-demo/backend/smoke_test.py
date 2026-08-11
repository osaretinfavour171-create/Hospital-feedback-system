"""Quick end-to-end validation of the HFD backend API (offline mode)."""
import sys

sys.path.insert(0, ".")

from fastapi.testclient import TestClient

import database
from main import app

client = TestClient(app)

with client:
    # 1. Health
    r = client.get("/api/v1/health")
    print("health:", r.status_code, r.json())

    # 2. Nurse feedback: positive rating -> no alert
    r = client.post("/api/v1/feedback/nurse", json={
        "visit_id": "VIS-2026-01",
        "department_id": "OPD",
        "overall_rating": 5,
        "category_tags": ["STAFF_COURTESY"],
        "raw_comment": "Great doctor attention.",
    })
    print("nurse-positive:", r.status_code, r.json())

    # 3. Nurse feedback: low rating -> alert generated
    r = client.post("/api/v1/feedback/nurse", json={
        "visit_id": "VIS-2026-02",
        "department_id": "EMERGENCY",
        "overall_rating": 1,
        "category_tags": ["LONG_WAIT"],
        "raw_comment": "Patient waited 4 hours.",
    })
    print("nurse-low:", r.status_code, r.json())

    # 4. WhatsApp: full conversational flow -> logged only on confirm
    phone = "+2348012345678"
    steps = [
        "The pharmacy was out of antibiotics and I waited 2 hours.",
        "2",
        "wait time and drug availability",
        "no",
        "yes",
    ]
    final = None
    for i, msg in enumerate(steps, 1):
        r = client.post("/api/v1/feedback/whatsapp/text", json={
            "phone_number": phone,
            "message_text": msg,
        })
        body = r.json()
        final = body
        print(f"whatsapp-turn{i}:", r.status_code,
              "| conv:", body.get("conversational"),
              "| step:", body.get("conversation_step"),
              "| fb:", body.get("feedback_id"))
    assert final and final.get("feedback_id"), "conversation should end with a logged feedback"
    print("whatsapp-text: OK ->", final["feedback_id"])

    # 5. WhatsApp text: medical advice -> guardrail (fresh phone, turn 1)
    r = client.post("/api/v1/feedback/whatsapp/text", json={
        "phone_number": "+2348011112222",
        "message_text": "What dosage of Amoxicillin should I give my child?",
    })
    print("whatsapp-guardrail:", r.status_code, r.json())
    assert r.json().get("guardrail_triggered"), "guardrail should fire"

    # 6. WhatsApp text: critical safety issue starts a conversation
    r = client.post("/api/v1/feedback/whatsapp/text", json={
        "phone_number": "+2348099990000",
        "message_text": "The nurse was abusive and shouted at my mother in the emergency room.",
    })
    print("whatsapp-critical:", r.status_code, "| conv:", r.json().get("conversational"),
          "| step:", r.json().get("conversation_step"))

    # 7. Dashboard metrics
    r = client.get("/api/v1/dashboard/metrics")
    print("metrics:", r.status_code, r.json())

    # 8. Alerts list
    r = client.get("/api/v1/dashboard/alerts")
    print("alerts:", r.status_code, len(r.json()))
    if r.json():
        alert_id = r.json()[0]["id"]
        # 9. Resolve first alert
        r2 = client.patch(f"/api/v1/alerts/{alert_id}", json={"status": "RESOLVED"})
        print("resolve:", r2.status_code, r2.json())

    # 10. Invalid department -> 422
    r = client.post("/api/v1/feedback/nurse", json={
        "visit_id": "VIS-2026-03",
        "department_id": "NOPE",
        "overall_rating": 3,
    })
    print("invalid-dept:", r.status_code)
    assert r.status_code == 422, "invalid department should be rejected"

print("\nALL CHECKS COMPLETE")
