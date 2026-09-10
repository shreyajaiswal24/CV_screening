"""Integration 1 - Google Drive (READ ONLY).

The trigger and the input. She drops CVs into a folder she already uses, so her
workflow does not change. Read-only by design: the system can never move,
rename or delete a candidate's file.
"""
from __future__ import annotations

import io
from pathlib import Path

from screening.config import ROOT, Secrets

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
MIME = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
    "application/vnd.google-apps.document": ".docx",   # exported
}


class DriveError(Exception):
    pass


def _service():
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        raise DriveError("Google integration needs extra packages. Run: "
                         "pip install google-api-python-client google-auth")
    path = ROOT / Secrets().google_credentials_path
    if not path.exists():
        raise DriveError(
            f"No Google credentials found at {path}. Either add the service-account "
            f"key file there, or leave drive_folder_id blank in config.yaml and "
            f"upload CVs directly instead.")
    creds = service_account.Credentials.from_service_account_file(str(path), scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def service_account_email() -> str:
    import json
    path = ROOT / Secrets().google_credentials_path
    if not path.exists():
        return ""
    return json.loads(path.read_text()).get("client_email", "")


def list_cvs(folder_id: str, seen_hashes: set[str] | None = None) -> list[dict]:
    """Files in the folder that look like CVs. Safe to call repeatedly."""
    svc = _service()
    try:
        resp = svc.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="files(id,name,mimeType,size,modifiedTime)",
            pageSize=200).execute()
    except Exception as e:
        raise DriveError(
            f"Couldn't read the Drive folder. Share it with {service_account_email()} "
            f"as a Viewer, and check drive_folder_id in config.yaml. ({e})")
    out = []
    for f in resp.get("files", []):
        if f["mimeType"] in MIME:
            out.append({"id": f["id"], "name": f["name"],
                        "mime": f["mimeType"], "size": f.get("size"),
                        "modified": f.get("modifiedTime")})
    return out


def download(file_id: str, name: str, dest_dir: Path | None = None) -> Path:
    from googleapiclient.http import MediaIoBaseDownload
    svc = _service()
    dest_dir = dest_dir or (ROOT / "data" / "_drive_cache")
    dest_dir.mkdir(parents=True, exist_ok=True)
    meta = svc.files().get(fileId=file_id, fields="mimeType,name").execute()
    mime = meta["mimeType"]

    if mime == "application/vnd.google-apps.document":
        req = svc.files().export_media(
            fileId=file_id,
            mimeType="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        ext = ".docx"
    else:
        req = svc.files().get_media(fileId=file_id)
        ext = MIME.get(mime, Path(name).suffix or ".bin")

    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, req)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    path = dest_dir / (Path(name).stem + ext)
    path.write_bytes(buf.getvalue())
    return path
