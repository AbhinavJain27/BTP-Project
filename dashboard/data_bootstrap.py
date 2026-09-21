from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASETS_ROOT = PROJECT_ROOT / "datasets"
MARKER = DATASETS_ROOT / ".bundle_ready"
ARCHIVE = PROJECT_ROOT / ".data_bundle.zip"

def _setting(name: str) -> str | None:
    try:
        value = st.secrets.get(name)
        if value:
            return str(value)
    except Exception:
        pass
    value = os.environ.get(name)
    return str(value) if value else None

def _download_http(url: str, dest: Path, status) -> None:
    import requests

    with requests.get(url, stream=True, timeout=120, allow_redirects=True) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length") or 0)
        done = 0
        with dest.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                handle.write(chunk)
                done += len(chunk)
                if total:
                    status.update(label=f"Downloading data bundle… {done / total:.0%}")

def _download_gdrive(file_id: str, dest: Path, status) -> None:
    import gdown

    status.update(label="Downloading data bundle from Google Drive…")
    gdown.download(id=file_id, output=str(dest), quiet=True, fuzzy=True)

@st.cache_resource(show_spinner=False)
def ensure_data() -> str:
    if MARKER.is_file():
        return "already present"

    if any(DATASETS_ROOT.glob("*/*/processed/extracted_network.parquet")):
        return "local data detected"

    url = _setting("DATA_BUNDLE_URL")
    gdrive_id = _setting("DATA_BUNDLE_GDRIVE_ID")
    if not url and not gdrive_id:
        st.error(
            "No data source configured. Set `DATA_BUNDLE_URL` (or `DATA_BUNDLE_GDRIVE_ID`) "
            "in this app's Secrets, then reboot the app."
        )
        st.stop()

    with st.status("Preparing river data (first run only)…", expanded=False) as status:
        try:
            if ARCHIVE.exists():
                ARCHIVE.unlink()
            if url:
                _download_http(url, ARCHIVE, status)
            else:
                _download_gdrive(gdrive_id, ARCHIVE, status)

            if not ARCHIVE.is_file() or ARCHIVE.stat().st_size < 1024:
                raise RuntimeError(
                    "The download produced no usable file. If you are using Google Drive, "
                    "confirm the link is shared as 'Anyone with the link' and that the daily "
                    "quota has not been exhausted."
                )

            status.update(label="Unpacking…")
            DATASETS_ROOT.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(ARCHIVE) as archive:

                for member in archive.namelist():
                    target = (DATASETS_ROOT / member).resolve()
                    if not str(target).startswith(str(DATASETS_ROOT.resolve())):
                        raise RuntimeError(f"Archive contains an unsafe path: {member}")
                archive.extractall(DATASETS_ROOT)

            entries = [p for p in DATASETS_ROOT.iterdir() if not p.name.startswith(".")]
            if len(entries) == 1 and entries[0].is_dir() and not any(
                (entries[0] / region).exists() for region in ("india", "global")
            ):
                inner = entries[0]
                for child in list(inner.iterdir()):
                    shutil.move(str(child), str(DATASETS_ROOT / child.name))
                inner.rmdir()

            ARCHIVE.unlink(missing_ok=True)
            MARKER.write_text("ok", encoding="utf-8")
            status.update(label="River data ready.", state="complete")
        except Exception as exc:
            ARCHIVE.unlink(missing_ok=True)
            status.update(label="Data preparation failed.", state="error")
            st.error(f"Could not prepare the data bundle: {exc}")
            st.stop()

    return "downloaded"
