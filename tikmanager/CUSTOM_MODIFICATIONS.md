# Custom Modifications to Tik Manager 4

## 1. Movie Ingestor (.mov support)
**File:** `tik_manager4/dcc/nuke/ingest/movie.py`
**Change:** Added new ingestor for .mov files
**Reason:** Tik Manager only supported image sequences by default

## 2. Movie Extractor
**File:** `tik_manager4/dcc/nuke/extract/movie.py`
**Change:** Added extractor for movie output
**Reason:** Publish only supported sequences, not movies

## 3. Valid Extensions
**File:** `tik_manager4/dcc/ingest_core.py`
**Line:** 43
**Change:** Added [".mov", ".mp4", ".avi"] to valid_extensions
**Reason:** Enable movie import

---
Last updated: 2025-01-17
```