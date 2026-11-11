"""DICOM scans: real DICOM only, identity removed, full quality kept, contrast, need-to-know sharing."""
import base64
from io import BytesIO

import numpy as np
import pydicom
from PIL import Image
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from tests.test_photos import refer


def make_dicom(modality="CT", photometric="MONOCHROME2"):
    """A small fake scan, written with the identifying fields a real scan machine adds."""
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"  # CT Image Storage
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = Dataset()
    ds.file_meta = meta
    ds.SOPClassUID, ds.SOPInstanceUID = meta.MediaStorageSOPClassUID, meta.MediaStorageSOPInstanceUID
    ds.PatientName = "Fake^Identifiable Person"
    ds.PatientID = "GH-NHIS-0000-FAKE"
    ds.PatientBirthDate = "19900101"
    ds.PatientSex = "F"
    ds.InstitutionName = "Fake Teaching Hospital"
    ds.ReferringPhysicianName = "Dr^Fake Referrer"
    ds.Modality, ds.BodyPartExamined, ds.StudyDate = modality, "CHEST", "20261101"
    ds.add_new(0x00091010, "LO", "private machine note")  # a manufacturer's private field
    ds.Rows, ds.Columns = 64, 80
    ds.SamplesPerPixel, ds.PhotometricInterpretation = 1, photometric
    ds.BitsAllocated, ds.BitsStored, ds.HighBit, ds.PixelRepresentation = 16, 12, 11, 0
    ds.RescaleIntercept, ds.RescaleSlope = -1024, 1  # stored 0..4095 -> -1024..3071 Hounsfield units
    ds.WindowCenter, ds.WindowWidth = 40, 400  # soft tissue
    pixels = np.tile(np.linspace(0, 4095, 80, dtype=np.uint16), (64, 1))  # dark-to-bright ramp
    ds.PixelData = pixels.tobytes()
    out = BytesIO()
    ds.save_as(out, enforce_file_format=True)
    return out.getvalue()


def b64(data):
    return base64.b64encode(data).decode()


def test_scan_deidentified_and_shared_on_need_to_know(client, login, make_patient, audit):
    chv, chv2, nurse, nurse2, pharm, ghs = (login(u) for u in ["chv1", "chv2", "nurse1", "nurse2", "pharm1", "ghs1"])
    patient = make_patient(chv)
    url = f"/patients/{patient['id']}/scans"
    body = {"caption": "Chest CT", "consent": True, "file": b64(make_dicom())}

    assert client.post(url, headers=nurse, json=body).status_code == 404  # not referred to this nurse yet
    refer(client, chv, patient)
    assert client.post(url, headers=chv, json=body).status_code == 403  # CHVs don't upload scans
    assert client.post(url, headers=nurse, json={**body, "consent": False}).status_code == 400
    assert client.post(url, headers=nurse, json=body).status_code == 200

    scan = client.get(url, headers=nurse).json()[0]
    assert (scan["modality"], scan["body_part"], scan["study_date"]) == ("CT", "CHEST", "2026-11-01")
    assert (scan["width"], scan["height"], scan["win_center"], scan["win_width"]) == (80, 64, 40, 400)
    assert (scan["value_min"], scan["value_max"]) == (-1024, 3071)  # real Hounsfield units
    assert "dicom" not in scan and "preview" not in scan

    # The stored file: identity gone, our patient code instead, scan data untouched
    file = client.get(f"/scans/{scan['id']}/dicom", headers=nurse)
    assert file.status_code == 200 and file.headers["cache-control"] == "no-store"
    assert file.headers["content-type"] == "application/dicom"
    ds = pydicom.dcmread(BytesIO(file.content))
    assert str(ds.PatientName) == patient["ref"] and ds.PatientID == patient["ref"]
    for gone in ["PatientBirthDate", "InstitutionName", "ReferringPhysicianName"]:
        assert gone not in ds
    assert (0x0009, 0x1010) not in ds and ds.PatientIdentityRemoved == "YES"
    for secret in [b"Identifiable", b"NHIS", b"19900101", b"Teaching Hospital", b"Referrer", b"private machine"]:
        assert secret not in file.content
    assert ds.PatientSex == "F" and ds.pixel_array.max() == 4095  # clinical facts and full 12-bit detail kept

    # Preview for phones: a JPEG; the CHV who referred can see it, but not download the full file
    preview = client.get(f"/scans/{scan['id']}/preview", headers=chv)
    assert preview.status_code == 200 and preview.content[:3] == b"\xff\xd8\xff"
    assert client.get(f"/scans/{scan['id']}/dicom", headers=chv).status_code == 403
    assert len(client.get(url, headers=chv).json()) == 1

    for outsider in [chv2, nurse2]:
        assert client.get(url, headers=outsider).status_code == 404
        assert client.get(f"/scans/{scan['id']}/preview", headers=outsider).status_code == 404
    for no_role in [pharm, ghs]:
        assert client.get(url, headers=no_role).status_code == 403
    assert {"upload_scan", "view_scan", "download_scan", "access_denied"} <= set(audit())

    assert client.delete(f"/scans/{scan['id']}", headers=login("doctor1")).status_code == 404  # only the uploader
    assert client.delete(f"/scans/{scan['id']}", headers=nurse).status_code == 200


def test_window_level_changes_contrast(client, login, make_patient):
    chv, nurse = login("chv1"), login("nurse1")
    patient = make_patient(chv)
    refer(client, chv, patient)
    client.post(f"/patients/{patient['id']}/scans", headers=nurse, json={"consent": True, "file": b64(make_dicom())})
    scan_id = client.get(f"/patients/{patient['id']}/scans", headers=nurse).json()[0]["id"]

    def middle_brightness(**window):
        res = client.get(f"/scans/{scan_id}/preview", headers=nurse, params=window)
        assert res.status_code == 200
        image = np.asarray(Image.open(BytesIO(res.content)).convert("L"), dtype=float)
        return image[:, 35:45].mean()  # the middle of the ramp is about 1000 HU

    soft_tissue = middle_brightness()               # default window 40 / 400: 1000 HU is far above it -> white
    bone = middle_brightness(center=1000, width=2000)  # bone window: 1000 HU is in the middle -> grey
    assert soft_tissue > 240 and 100 < bone < 160
    assert client.get(f"/scans/{scan_id}/preview", headers=nurse, params={"center": 0, "width": 0}).status_code == 422


def test_only_real_dicom_accepted(client, login, make_patient):
    chv, nurse = login("chv1"), login("nurse1")
    patient = make_patient(chv)
    refer(client, chv, patient)
    url = f"/patients/{patient['id']}/scans"
    jpeg = b"\xff\xd8\xff\xe0" + b"not a scan" * 20
    for bad in [b64(jpeg), "not base64!!"]:
        res = client.post(url, headers=nurse, json={"consent": True, "file": bad})
        assert res.status_code == 400 and "DICOM" in res.json()["detail"]


def test_monochrome1_is_inverted(client, login, make_patient):
    """Some X-ray machines store bright bone as LOW numbers (MONOCHROME1): the preview must flip it."""
    chv, nurse = login("chv1"), login("nurse1")
    patient = make_patient(chv)
    refer(client, chv, patient)
    url = f"/patients/{patient['id']}/scans"
    client.post(url, headers=nurse, json={"consent": True, "file": b64(make_dicom("CR", "MONOCHROME1"))})
    scan_id = client.get(url, headers=nurse).json()[0]["id"]
    image = np.asarray(Image.open(BytesIO(client.get(f"/scans/{scan_id}/preview", headers=nurse).content)).convert("L"))
    assert image[:, :5].mean() > 200 and image[:, -5:].mean() < 50  # low values shown bright
