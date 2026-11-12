"""Clinical photos and image sharing: wounds, skin conditions, X-rays, lab results.

- A CHV photographs a wound or rash with the phone camera; a nurse or doctor can add an
  X-ray or lab result. The phone shrinks each photo (about 150 KB) so it uploads on 2G.
- The patient must agree to each photo (Act 843: health images are sensitive data).
- Who sees them: the patient's own CHV, and staff at facilities the patient was referred to.
  Never pharmacists or GHS. Every upload and every view is in the audit log.
"""
import base64
import binascii

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from auth import require_role
from database import get_db, log_access, now_text

router = APIRouter()
MAX_BYTES = 400_000  # after shrinking on the phone; refuses full-size camera files
TYPES = {"image/jpeg", "image/png", "image/webp"}
MAGIC = {b"\xff\xd8\xff": "image/jpeg", b"\x89PNG": "image/png", b"RIFF": "image/webp"}  # first bytes of each format


class PhotoIn(BaseModel):
    kind: str = Field(pattern=r"^(wound|skin|xray|lab|other)$")
    caption: str = Field(default="", max_length=1000)  # 200 typed; longer when end-to-end encrypted
    consent: bool  # the patient agreed to this photo
    image: str     # data URL: "data:image/jpeg;base64,...."; encrypted: base64 of the locked bytes
    encrypted: bool = False  # locked on the phone with the patient's key (e2e.py): the server cannot see it


def check_access(conn, patient_id, user):
    """Need-to-know: the patient's CHV, or staff at a facility the patient was referred to."""
    if user["role"] == "chv":
        ok = conn.execute("SELECT ref FROM patients WHERE id = ? AND chv_id = ?", (patient_id, user["id"])).fetchone()
    else:
        ok = conn.execute("SELECT p.ref FROM patients p JOIN referrals r ON r.patient_id = p.id "
                          "WHERE p.id = ? AND r.facility = ? LIMIT 1", (patient_id, user["facility"])).fetchone()
    if not ok:
        log_access(conn, user["id"], "access_denied", f"photos:patient:{patient_id}")
        conn.commit()
        conn.close()
        raise HTTPException(status_code=404, detail="Patient not found")
    return ok["ref"]


def decode(data_url):
    try:
        header, b64 = data_url.split(",", 1)
        declared = header.split(":")[1].split(";")[0]
        data = base64.b64decode(b64, validate=True)
    except (ValueError, IndexError, binascii.Error):
        raise HTTPException(status_code=400, detail="This file is not a photo")
    real = next((t for magic, t in MAGIC.items() if data.startswith(magic)), None)
    if declared not in TYPES or real != declared:  # check the bytes, not just the name
        raise HTTPException(status_code=400, detail="Only JPEG, PNG or WebP photos")
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="Photo too large. Please try again.")
    return declared, data


@router.post("/patients/{patient_id}/photos")
def upload(patient_id: int, body: PhotoIn, user=Depends(require_role("chv", "nurse", "doctor"))):
    if not body.consent:
        raise HTTPException(status_code=400, detail="The patient must agree before a photo is taken")
    if body.encrypted:
        # We cannot check what is inside (that is the point), only the size
        try:
            data = base64.b64decode(body.image, validate=True)
        except (ValueError, binascii.Error):
            raise HTTPException(status_code=400, detail="This file is not a photo")
        if len(data) > MAX_BYTES:
            raise HTTPException(status_code=400, detail="Photo too large. Please try again.")
        content_type = "application/octet-stream"
    else:
        if len(body.caption) > 200:
            raise HTTPException(status_code=422, detail="Caption can be at most 200 characters")
        content_type, data = decode(body.image)
    conn = get_db()
    ref = check_access(conn, patient_id, user)
    conn.execute("INSERT INTO photos (patient_id, uploaded_by, kind, caption, content_type, size, data, encrypted, created_at) "
                 "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                 (patient_id, user["id"], body.kind, body.caption.strip() or None, content_type, len(data), data,
                  1 if body.encrypted else 0, now_text()))
    log_access(conn, user["id"], "upload_photo", f"{ref} {body.kind}")
    conn.commit()
    conn.close()
    return {"success": True}


@router.get("/patients/{patient_id}/photos")
def list_photos(patient_id: int, user=Depends(require_role("chv", "nurse", "doctor"))):
    conn = get_db()
    ref = check_access(conn, patient_id, user)
    rows = conn.execute("SELECT ph.id, ph.kind, ph.caption, ph.size, ph.encrypted, ph.created_at, ph.uploaded_by, "
                        "u.full_name AS uploaded_by_name, u.role AS uploaded_by_role, u.facility AS uploaded_by_facility "
                        "FROM photos ph JOIN users u ON u.id = ph.uploaded_by WHERE ph.patient_id = ? ORDER BY ph.id DESC",
                        (patient_id,)).fetchall()
    log_access(conn, user["id"], "list_photos", ref)
    conn.commit()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/photos/{photo_id}")
def view(photo_id: int, user=Depends(require_role("chv", "nurse", "doctor"))):
    conn = get_db()
    photo = conn.execute("SELECT * FROM photos WHERE id = ?", (photo_id,)).fetchone()
    if not photo:
        conn.close()
        raise HTTPException(status_code=404, detail="Photo not found")
    ref = check_access(conn, photo["patient_id"], user)
    log_access(conn, user["id"], "view_photo", f"{ref} photo:{photo_id}")
    conn.commit()
    conn.close()
    # no-store: a health photo must not stay in a shared phone's cache
    return Response(content=bytes(photo["data"]), media_type=photo["content_type"],
                    headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.delete("/photos/{photo_id}")
def remove(photo_id: int, user=Depends(require_role("chv", "nurse", "doctor"))):
    """Only the person who took a photo can delete it (e.g. wrong patient)."""
    conn = get_db()
    photo = conn.execute("SELECT patient_id, uploaded_by FROM photos WHERE id = ?", (photo_id,)).fetchone()
    if not photo or photo["uploaded_by"] != user["id"]:
        conn.close()
        raise HTTPException(status_code=404, detail="Photo not found")
    conn.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
    log_access(conn, user["id"], "delete_photo", f"photo:{photo_id}")
    conn.commit()
    conn.close()
    return {"success": True}
