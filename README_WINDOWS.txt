SUBSYSTEM EXTRACTOR v8 (UNIFIED) — WINDOWS INSTRUCTIONS
========================================================

WHAT IT DOES
------------
One tool for BOTH drawing families. Dump all your layered sets in one
folder, run it once, and it builds one PDF per subsystem per plant per
drawing type — only the pages that subsystem appears on, isolated to
that subsystem.

It tells the two families apart by itself, file by file:
  * Bluebeam systemized sets — subsystem layers are markup annotations
    (layers named 33-05 etc.). Other subsystems' markups are REMOVED
    from each output, because Bluebeam does not reliably honor layer
    on/off for markups.
  * SPPID/AutoCAD P&IDs — subsystem layers are drawing content (layers
    named 33-05 or "Subsystem 33-05"). Other subsystem layers are
    switched OFF but stay in the file, toggleable in your viewer.

The plant for every page is read from that drawing's own document
number (WG.. -> WOC, WF.. -> WCF, BT10 -> BT1, BT20 -> BT2,
BT30 -> BT3), so a MIXED-plant file (like the Group1/Group2 layered
P&ID PDFs) splits into per-plant outputs automatically. The filename
plant is only a fallback for pages with no readable code.

UNLAYERED DRAWINGS: a drawing with no subsystem layers at all —
an unlayered page inside a layered set, or a whole set that was
never layered — is routed by the subsystem break labels printed on
the drawing itself, and is filed whole into each of its subsystems'
outputs. Nothing is switched off on those pages (there are no
layers), so all subsystems' colors still show. Pages that DO have
layers are always routed by their layers, never by labels.

The base drawing, legend, and unlayered markups are always left
untouched, and your original PDFs are never modified.


WHERE THE OUTPUT GOES
---------------------
Everything lands in a folder tree under output\:

    output\
      WCF\
        46\
          46-01\
            WCF 46-01 - Systemized PIDs (Layered).pdf
            WCF 46-01 - Systemized SLDs (Layered).pdf
          46-02\
            ...
      BT1\
        ...

  * First level: the PLANT (BT1, BT2, BT3, WCF, WOC, KPAD, ...)
  * Second level: the SYSTEM — the first two digits of the subsystem
    (46-01 and 46-02 both live under system folder 46)
  * Third level: the SUBSYSTEM folder — every drawing type for that
    subsystem (PIDs, SLDs, Panel Schedules, ICS BKDs, Telecom BKDs,
    Automation BKDs, ...) lands side by side in it.
  * File names:  <PLANT> <NN-NN> - Systemized <TYPE> (Layered).pdf

The folders are created the first time they're needed and then left
alone — when you re-run the tool, it just updates the files inside
the correct folders. Nothing is wiped between runs.


ONE-TIME SETUP (per computer)
-----------------------------
Open Command Prompt and run this ONE command (one time only):

    python -m pip install pymupdf


HOW TO RUN
----------
Option A — double-click:
  1. Copy every PDF you want processed into this folder (next to
     extract_all.py). Set files should be named like:
         WCF Systemized SLDs.pdf
         KPAD Systemized Panel Schedules.pdf
         BT2 Systemized ICS Block Diagrams.pdf
     Old group files like Group1_Layered_Drawings.pdf also work —
     they're treated as P&IDs, plant from the document numbers.
  2. Double-click run_all.bat. It asks:
         Which subsystems? Type one (33-05), several (33-05 50-08),
         or just press Enter for ALL:

Option B — Command Prompt (same folder):
    python extract_all.py            <- all subsystems
    python extract_all.py 33-05      <- one
    python extract_all.py 33-05 50-08 23-71   <- several

NOTES
-----
  * v8 fixes the plant on BT drawings: every P&ID references the
    common WFXX legend sheets, which used to tie with the drawing's
    own BT number and could win, filing BT drawings under WCF.
    Ties are now broken by the code's total mentions on the page
    (the drawing's own number repeats in its title block), then by
    the filename plant. If you extracted BT Group files with v5–v7,
    re-run them with v8 — some drawings were filed under WCF.
  * If an output PDF is OPEN in your viewer (or being synced) when
    the tool tries to update it, that one subsystem is skipped with
    a "!! SKIPPED" line and the run carries on — the old file stays
    as it was. Close the PDF and re-run just that number to fill
    the gap. The end of the run lists everything that was skipped.
  * Big files take a while (the tool rebuilds the PDF once per
    subsystem per plant per type).
  * A file with no subsystem layers yet (e.g. unlayered PFDs) is
    routed by its printed break labels instead — see UNLAYERED
    DRAWINGS above. A file with neither layers nor labels is
    skipped with a message.
  * A requested subsystem that isn't in a file gets a NOTE line and
    the run carries on.
  * Block-diagram types are shortened to "BKDs" in output names
    (Telecom/ICS/Automation ... -> Telecom BKDs / ICS BKDs /
    Automation BKDs). Everything else is used as written. To change
    a label, edit DOCTYPE_MAP in config.py.
