import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Literal, Any, Dict
from datetime import datetime
from bson import ObjectId

from database import db, create_document, get_documents

app = FastAPI(title="Driver Attendance API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utilities

def serialize_id(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return doc
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    return d


def normalize_date(date_str: str) -> str:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")


# Schemas (request bodies)
class DriverCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    license_no: Optional[str] = None


class AttendanceCreate(BaseModel):
    driver_id: str
    date: str
    status: Literal['present', 'absent', 'late'] = 'present'
    notes: Optional[str] = None


@app.get("/")
def root():
    return {"message": "Driver Attendance Backend running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            try:
                response["collections"] = db.list_collection_names()[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:50]}"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response


# Driver endpoints
@app.post("/drivers")
def create_driver(payload: DriverCreate):
    driver = payload.model_dump()
    new_id = create_document("driver", driver)
    doc = db["driver"].find_one({"_id": ObjectId(new_id)})
    return serialize_id(doc)


@app.get("/drivers")
def list_drivers():
    docs = get_documents("driver")
    return [serialize_id(d) for d in docs]


# Attendance endpoints
@app.post("/attendance")
def mark_attendance(payload: AttendanceCreate):
    # validate driver exists
    try:
        driver_obj_id = ObjectId(payload.driver_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid driver_id")

    driver = db["driver"].find_one({"_id": driver_obj_id})
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    date_norm = normalize_date(payload.date)

    # upsert: ensure single record per driver per date
    existing = db["attendance"].find_one({"driver_id": payload.driver_id, "date": date_norm})
    data = {
        "driver_id": payload.driver_id,
        "date": date_norm,
        "status": payload.status,
        "notes": payload.notes,
    }
    if existing:
        db["attendance"].update_one({"_id": existing["_id"]}, {"$set": {**data, "updated_at": datetime.utcnow()}})
        doc = db["attendance"].find_one({"_id": existing["_id"]})
    else:
        new_id = create_document("attendance", data)
        doc = db["attendance"].find_one({"_id": ObjectId(new_id)})
    return serialize_id(doc)


@app.get("/attendance")
def get_attendance(date: Optional[str] = Query(None), driver_id: Optional[str] = Query(None)):
    filter_q: Dict[str, Any] = {}
    if date:
        filter_q["date"] = normalize_date(date)
    if driver_id:
        try:
            ObjectId(driver_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid driver_id")
        filter_q["driver_id"] = driver_id
    docs = get_documents("attendance", filter_q)
    return [serialize_id(d) for d in docs]


@app.get("/attendance/summary")
def attendance_summary(driver_id: str = Query(...)):
    try:
        ObjectId(driver_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid driver_id")

    pipeline = [
        {"$match": {"driver_id": driver_id}},
        {"$group": {
            "_id": "$status",
            "count": {"$sum": 1}
        }}
    ]
    results = list(db["attendance"].aggregate(pipeline))
    counts = {r["_id"]: r["count"] for r in results}
    total_days = sum(counts.values())
    return {
        "driver_id": driver_id,
        "total_days": total_days,
        "present": counts.get("present", 0),
        "absent": counts.get("absent", 0),
        "late": counts.get("late", 0),
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
