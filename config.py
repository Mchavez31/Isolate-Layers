# ---- BATCH SETTINGS (v2) ----
# run_all.bat / extract_all.py processes EVERY PDF in this folder whose
# name looks like "<PLANT> Systemized <DOC TYPE>.pdf"
# (hyphen style "WCF-Systemized-SLDs.pdf" also works).
# Plant and doc type come from the filename, so no per-file editing.

# Output label for each doc type as it appears in the source filename.
# Michael's naming: block diagrams are "BKDs" in output names.
DOCTYPE_MAP = {
    "Telecom Diagrams": "Telecom BKDs",
    "Telecom Block Diagrams": "Telecom BKDs",
    "Automation Block Diagrams": "Automation BKDs",
    "ICS Block Diagrams": "ICS BKDs",
    # anything not listed here is used exactly as written, e.g.
    # "SLDs", "Panel Schedules", "PFDs", "P&IDs", "Overall SLDs",
    # "ICS GARs", "ICS BKDs", "Combined P&ID Sketches"
}

# Folder where the per-subsystem PDFs will be written (created if missing).
OUTPUT_DIR = "output"

# Working files (created if missing).
WORK_DIR = "work"

# ---- SINGLE-FILE SETTINGS (steps 1-3, used only if you run them by hand) ----
SOURCE_PDF = "WCF_Systemized_SLDs.pdf"
DOC_TYPE = "SLDs"

# Plant code -> plant name for single-file mode. The code is the segment
# after "WILG-" in the document number. Prefix rules (per Michael):
#   WG* -> WOC,  WF* -> WCF,  BT10 -> BT1, BT20 -> BT2, BT30 -> BT3.
def plant_of_code(code):
    if code.startswith("WG"):
        return "WOC"
    if code.startswith("WF"):
        return "WCF"
    return {"BT10": "BT1", "BT20": "BT2", "BT30": "BT3"}.get(code)


# Layers that stay ON in every output file, alongside the target subsystem.
# Set to None to keep ALL non-subsystem layers on.
BASE_LAYERS = None
