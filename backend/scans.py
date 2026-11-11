"""Medical scans in DICOM, the file format every hospital X-ray, CT and ultrasound machine uses.

Why not just a photo of the X-ray? A photo loses detail and contrast. A DICOM file keeps every
grey level the machine measured (often 4,096 levels, while a JPEG has 256), plus facts about the scan
(what kind, which body part, when). A doctor can then change the contrast ("window/level") to see
bone or soft tissue, and can open the original file in any hospital DICOM viewer.

What happens to an uploaded file:
1. Check it really is DICOM (the letters "DICM" at byte 128), and at most 25 MB.
2. De-identify (Act 843, data minimisation): the scan machine wrote the patient's name, ID,
   birth date, address, and staff and hospital names into the file. We delete them and put our
   own patient code (e.g. HC-1A2B) instead. Hidden "private" manufacturer fields are deleted too.
3. Make a small JPEG preview (max 1024 px) for phones and 2G, using the scan's own contrast.
4. Keep the de-identified DICOM at full quality, in the encrypted database.

Who: nurses and doctors upload (scans come from facility machines). The same people who can
see the patient's photos can see the preview; only nurses and doctors can download the full file.
Every upload, view and download is in the audit log.

Formats read: uncompressed, RLE, JPEG and JPEG 2000 (tested with pydicom's sample scans).
Limits (honest): rarer compressed formats (e.g. JPEG-LS, lossless JPEG) are refused with a
message; text "burned into" the image pixels (common on ultrasound) cannot be removed, so the
app shows a warning when the file says it has some. Previews are not for diagnosis on a phone.
"""
import base64
import binascii
from io import BytesIO

import numpy as np
import pydicom
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from PIL import Image
from pydantic import BaseModel, Field
from pydicom.pixels import apply_modality_lut

from auth import require_role
from database import get_db, log_access, now_text
from photos import check_access

router = APIRouter()
MAX_BYTES = 25_000_000
PREVIEW_SIDE = 1024

# Fields that identify a person. Removed from every file (DICOM PS3.15 "basic profile", shortened).
IDENTIFYING = [
    "PatientName", "PatientID", "PatientBirthDate", "PatientBirthTime", "PatientAddress",
    "PatientTelephoneNumbers", "OtherPatientIDs", "OtherPatientNames", "OtherPatientIDsSequence",
    "PatientMotherBirthName", "IssuerOfPatientID", "MedicalRecordLocator", "PatientComments",
    "EthnicGroup", "MilitaryRank", "ReferringPhysicianName", "PerformingPhysicianName",
    "PhysiciansOfRecord", "NameOfPhysiciansReadingStudy", "RequestingPhysician", "OperatorsName",
    "InstitutionName", "InstitutionAddress", "InstitutionalDepartmentName", "StationName",
    "AccessionNumber", "DeviceSerialNumber",
]


class ScanIn(BaseModel):
    caption: str = Field(default="", max_length=200)
    consent: bool  # the patient agreed to this scan being stored and shared
    file: str      # the .dcm file, base64


def read_dicom(data):
    try:
        return pydicom.dcmread(BytesIO(data))  # refuses files without the DICOM marker
    except Exception:  # InvalidDicomError, or a damaged file
        raise HTTPException(status_code=400, detail="This is not a DICOM scan file (.dcm)")


def deidentify(ds, ref):
    for name in IDENTIFYING:
        if name in ds:
            delattr(ds, name)
    ds.remove_private_tags()
    ds.PatientName = ref  # our patient code, so the file still belongs to the right record
    ds.PatientID = ref
    ds.PatientIdentityRemoved = "YES"
    ds.DeidentificationMethod = "HealthConnect: identity fields removed"  # max 64 characters


def first(value):
    """Some fields hold several values (e.g. two contrast settings): use the first."""
    if value is None:
        return None
    try:
        return float(value[0])
    except TypeError:
        return float(value)


def grey_values(ds):
    """The scan's grey values in real units (e.g. Hounsfield units on CT), middle frame if a video."""
    try:
        pixels = ds.pixel_array
    except Exception:
        raise HTTPException(status_code=400, detail="This scan is compressed in a format we cannot read. "
                                                    "Export it from the machine as uncompressed DICOM.")
    if int(getattr(ds, "NumberOfFrames", 1) or 1) > 1:
        pixels = pixels[len(pixels) // 2]
    if getattr(ds, "SamplesPerPixel", 1) == 3:
        return pixels, True  # colour (e.g. Doppler ultrasound): show as it is
    return apply_modality_lut(pixels, ds).astype(np.float64), False


def default_window(ds, values):
    """The contrast the machine suggests; if none, ignore the darkest and brightest 0.5%."""
    center, width = first(ds.get("WindowCenter")), first(ds.get("WindowWidth"))
    if center is None or not width:
        low, high = np.percentile(values, [0.5, 99.5])
        center, width = (low + high) / 2, max(high - low, 1)
    return center, width


def render(ds, values, colour, center, width):
    """Window/level: values from center - width/2 (black) to center + width/2 (white)."""
    if colour:
        image = Image.fromarray(values.astype(np.uint8), "RGB")
    else:
        low = center - width / 2
        grey = np.clip((values - low) / max(width, 1), 0, 1) * 255
        if getattr(ds, "PhotometricInterpretation", "") == "MONOCHROME1":
            grey = 255 - grey  # this format stores bright as low numbers
        image = Image.fromarray(grey.astype(np.uint8), "L")
    image.thumbnail((PREVIEW_SIDE, PREVIEW_SIDE))
    out = BytesIO()
    image.save(out, "JPEG", quality=85)
    return out.getvalue()


def text(ds, name):
    value = ds.get(name)
    return str(value).strip() or None if value is not None else None


@router.post("/patients/{patient_id}/scans")
def upload(patient_id: int, body: ScanIn, user=Depends(require_role("nurse", "doctor"))):
    if not body.consent:
        raise HTTPException(status_code=400, detail="The patient must agree before a scan is stored")
    try:
        data = base64.b64decode(body.file, validate=True)
    except (ValueError, binascii.Error):
        raise HTTPException(status_code=400, detail="This is not a DICOM scan file (.dcm)")
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="Scan too large (25 MB at most)")
    ds = read_dicom(data)
    values, colour = grey_values(ds)
    center, width = (None, None) if colour else default_window(ds, values)
    preview = render(ds, values, colour, center, width)

    conn = get_db()
    ref = check_access(conn, patient_id, user)
    deidentify(ds, ref)
    out = BytesIO()
    ds.save_as(out, enforce_file_format=True)
    clean = out.getvalue()
    study_date = text(ds, "StudyDate")
    if study_date and len(study_date) == 8:
        study_date = f"{study_date[:4]}-{study_date[4:6]}-{study_date[6:]}"
    conn.execute(
        "INSERT INTO scans (patient_id, uploaded_by, caption, modality, body_part, study_date, width, height, frames, "
        "win_center, win_width, value_min, value_max, burned_in, size, dicom, preview, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (patient_id, user["id"], body.caption.strip() or None, text(ds, "Modality"), text(ds, "BodyPartExamined"),
         study_date, int(ds.Columns), int(ds.Rows), int(getattr(ds, "NumberOfFrames", 1) or 1),
         center, width, None if colour else float(values.min()), None if colour else float(values.max()),
         1 if text(ds, "BurnedInAnnotation") == "YES" else 0, len(clean), clean, preview, now_text()))
    log_access(conn, user["id"], "upload_scan", f"{ref} {text(ds, 'Modality') or 'scan'}")
    conn.commit()
    conn.close()
    return {"success": True}


@router.get("/patients/{patient_id}/scans")
def list_scans(patient_id: int, user=Depends(require_role("chv", "nurse", "doctor"))):
    conn = get_db()
    ref = check_access(conn, patient_id, user)
    rows = conn.execute(
        "SELECT s.id, s.caption, s.modality, s.body_part, s.study_date, s.width, s.height, s.frames, s.win_center, "
        "s.win_width, s.value_min, s.value_max, s.burned_in, s.size, s.created_at, s.uploaded_by, "
        "u.full_name AS uploaded_by_name, u.facility AS uploaded_by_facility "
        "FROM scans s JOIN users u ON u.id = s.uploaded_by WHERE s.patient_id = ? ORDER BY s.id DESC",
        (patient_id,)).fetchall()
    log_access(conn, user["id"], "list_scans", ref)
    conn.commit()
    conn.close()
    return [dict(r) for r in rows]


def load_scan(conn, scan_id, user, action):
    scan = conn.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
    if not scan:
        conn.close()
        raise HTTPException(status_code=404, detail="Scan not found")
    ref = check_access(conn, scan["patient_id"], user)
    log_access(conn, user["id"], action, f"{ref} scan:{scan_id}")
    conn.commit()
    return scan, ref


NO_STORE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}  # not kept on a shared phone


@router.get("/scans/{scan_id}/preview")
def preview(scan_id: int, center: float | None = Query(None), width: float | None = Query(None, gt=0),
            user=Depends(require_role("chv", "nurse", "doctor"))):
    """JPEG of the scan. With center + width: the doctor's own contrast (e.g. bone or soft tissue)."""
    conn = get_db()
    scan, _ = load_scan(conn, scan_id, user, "view_scan")
    conn.close()
    if center is None or width is None:
        image = bytes(scan["preview"])
    else:
        ds = pydicom.dcmread(BytesIO(bytes(scan["dicom"])))
        values, colour = grey_values(ds)
        image = render(ds, values, colour, center, width)
    return Response(content=image, media_type="image/jpeg", headers=NO_STORE)


@router.get("/scans/{scan_id}/dicom")
def download(scan_id: int, user=Depends(require_role("nurse", "doctor"))):
    """The full-quality (de-identified) file, to open in a hospital DICOM viewer."""
    conn = get_db()
    scan, ref = load_scan(conn, scan_id, user, "download_scan")
    conn.close()
    return Response(content=bytes(scan["dicom"]), media_type="application/dicom",
                    headers={**NO_STORE, "Content-Disposition": f'attachment; filename="{ref}-scan-{scan_id}.dcm"'})


@router.delete("/scans/{scan_id}")
def remove(scan_id: int, user=Depends(require_role("nurse", "doctor"))):
    """Only the person who uploaded a scan can delete it (e.g. wrong patient)."""
    conn = get_db()
    scan = conn.execute("SELECT uploaded_by FROM scans WHERE id = ?", (scan_id,)).fetchone()
    if not scan or scan["uploaded_by"] != user["id"]:
        conn.close()
        raise HTTPException(status_code=404, detail="Scan not found")
    conn.execute("DELETE FROM scans WHERE id = ?", (scan_id,))
    log_access(conn, user["id"], "delete_scan", f"scan:{scan_id}")
    conn.commit()
    conn.close()
    return {"success": True}
