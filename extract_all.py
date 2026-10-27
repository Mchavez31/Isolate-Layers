#!/usr/bin/env python3
"""Unified batch extractor (v7): process every PDF in this folder.

Handles BOTH drawing families and tells them apart per file:
  * Bluebeam systemized sets ("<PLANT> Systemized <TYPE>.pdf") whose
    subsystem layers are markup annotations, and
  * SPPID/AutoCAD layered P&IDs, whose subsystem layers are drawing
    content (layer names "NN-NN" or "Subsystem NN-NN"), including
    mixed-plant files whose name carries no plant (e.g.
    Group1_Layered_Drawings.pdf).

Pages with NO subsystem layers at all — unlayered drawings inside a
layered set, or a whole set that was never layered (e.g. the PFDs) —
are routed by the subsystem break labels printed on the drawing, and
go into the output whole (nothing to switch off, all colors showing).
Layered pages are never label-routed: when a page has layers, the
layers rule.

Plant for each page comes from the page's own document number
(WG* -> WOC, WF* -> WCF, BT10 -> BT1, BT20 -> BT2, BT30 -> BT3),
with the filename plant as fallback — so a mixed-plant P&ID file
splits into per-plant outputs automatically.

For each subsystem at each plant: only that subsystem's pages, with
only that subsystem's markups kept (annotation files) and the layer
defaults set to show just that subsystem + base layers.

Outputs go to output/<PLANT>/<system>/<subsystem>/, named
"<PLANT> <NN-NN> - Systemized <TYPE> (Layered).pdf" (system = first
two digits of the subsystem). Folders persist between runs; re-runs
update the files in place. The original PDFs are never modified.
"""
import glob
import json
import os
import re
import sys
import zlib
from collections import Counter, defaultdict

import pymupdf

import config

SUB_RE = re.compile(r"^\d\d-\d\d$")
SUB_NAME_RE = re.compile(r"^(?:Subsystem )?(\d\d-\d\d)$")
CODE_RE = re.compile(r"WILG-([A-Z0-9]+)-")
LOOSE_RE = re.compile(r"\b([A-Z]{2}[A-Z0-9]{2})\b")


def parse_filename(path):
    """'<PLANT> Systemized <TYPE>.pdf' -> (plant, doc_type) or None.

    Accepts space, hyphen, or underscore separators
    ("WCF Systemized SLDs.pdf", "WCF-Systemized-SLDs.pdf",
    "WCF_Systemized_Panel_Schedules.pdf").
    """
    stem = os.path.splitext(os.path.basename(path))[0]
    for sep in (" Systemized ", "-Systemized-", "_Systemized_"):
        if sep in stem:
            plant, dtype = stem.split(sep, 1)
            plant = plant.strip()
            dtype = dtype.strip().replace("_", " ").replace("-", " ")
            dtype = " ".join(dtype.split())
            dtype = config.DOCTYPE_MAP.get(dtype, dtype)
            return plant, dtype
    return None


# ---------- step 1a: subsystem pages from markup annotations ----------
def map_annotations(doc):
    xref_to_name = {x: info["name"] for x, info in doc.get_ocgs().items()}
    subsys_pages = defaultdict(set)
    base_used = set()
    for i in range(doc.page_count):
        for a in doc[i].annots() or []:
            t, v = doc.xref_get_key(a.xref, "OC")
            if t == "null":
                continue
            try:
                name = xref_to_name.get(int(v.split()[0]))
            except (ValueError, IndexError):
                continue
            if not name:
                continue
            if SUB_RE.match(name):
                subsys_pages[name].add(i + 1)
            else:
                base_used.add(name)
    return subsys_pages, base_used


# ---------- step 1b: subsystem pages from layered drawing content ----
def _page_used_layers(doc, xref_to_name, page):
    res_key = doc.xref_get_key(page.xref, "Resources")
    res_obj = doc.xref_object(res_key[1]) if res_key[0] == "xref" else res_key[1]
    prop_map = {}
    m = re.search(r"/Properties\s*(?:(\d+) 0 R|<<(.*?)>>)", res_obj, re.S)
    if m:
        prop_obj = doc.xref_object(int(m.group(1))) if m.group(1) else m.group(2)
        for mm in re.finditer(r"/oc(\d+)\s+(\d+) 0 R", prop_obj):
            ocg_xref = int(mm.group(2))
            if ocg_xref in xref_to_name:
                prop_map["oc" + mm.group(1)] = xref_to_name[ocg_xref]
    data = b""
    for c in page.get_contents():
        raw = doc.xref_stream_raw(c)
        if raw:
            try:
                data += zlib.decompress(raw)
            except Exception:
                data += raw
    used = set()
    for mm in re.finditer(rb"/OC\s*/(oc\d+)\s*BDC", data):
        key = mm.group(1).decode()
        if key in prop_map:
            used.add(prop_map[key])
    return used


def map_content(doc):
    xref_to_name = {x: info["name"] for x, info in doc.get_ocgs().items()}
    subsys_pages = defaultdict(set)
    base_used = set()
    for i in range(doc.page_count):
        for name in _page_used_layers(doc, xref_to_name, doc[i]):
            m = SUB_NAME_RE.match(name)
            if m:
                subsys_pages[m.group(1)].add(i + 1)
            else:
                base_used.add(name)
    return subsys_pages, base_used


# ---------- step 1c: subsystem pages from printed break labels --------
# For pages with NO subsystem layers at all (unlayered P&IDs, or a mixed
# file where some pages were never marked up): the subsystem numbers are
# read from the break labels printed on the drawing -- the same label text
# the review tool's check #1 already reads via plain get_text().
def map_labels(doc, skip_pages):
    subsys_pages = defaultdict(set)
    for i in range(doc.page_count):
        if (i + 1) in skip_pages:
            continue
        dd = doc[i].get_text("dict")
        subs = set()
        for b in dd["blocks"]:
            for l in b.get("lines", []):
                for s in l["spans"]:
                    t = s["text"].strip()
                    if SUB_RE.match(t):
                        subs.add(t)
        for n in subs:
            subsys_pages[n].add(i + 1)
    return subsys_pages


# ---------- step 3: build one output PDF ----------
def output_path(plant, dtype, subsys):
    """output/<PLANT>/<system>/<subsystem>/
       '<PLANT> <NN-NN> - Systemized <TYPE> (Layered).pdf'

    System = first two digits of the subsystem (46-01 -> folder 46).
    Folders are created as needed and never removed, so re-runs update
    the same files in the same folders."""
    system = subsys.split("-")[0]
    folder = os.path.join(config.OUTPUT_DIR, plant, system, subsys)
    os.makedirs(folder, exist_ok=True)
    label = dtype.replace("P&IDs", "PIDs").replace("P&ID", "PID")
    name = f"{plant} {subsys} - Systemized {label} (Layered).pdf"
    return os.path.join(folder, name)


def build_one(src_path, plant, dtype, subsys, pages, mode):
    new = pymupdf.open(src_path)
    keep = set(pages)
    new.delete_pages([i for i in range(new.page_count) if (i + 1) not in keep])
    n2x = {info["name"]: x for x, info in new.get_ocgs().items()}
    # the target layer may be named "NN-NN" or "Subsystem NN-NN"
    target_name = subsys if subsys in n2x else f"Subsystem {subsys}"
    base_on = [n for n in n2x
               if not SUB_NAME_RE.match(n) and n != target_name]
    if config.BASE_LAYERS is not None:
        base_on = [n for n in base_on if n in config.BASE_LAYERS]
    keep_layers = set(base_on) | {target_name}
    if mode == "annotations":
        # Bluebeam ignores layer on/off for markups, so remove the other
        # subsystems' markups outright. Base/unlayered markups stay.
        x2n = {x: n for n, x in n2x.items()}
        for page in new:
            while True:
                doomed = None
                for annot in page.annots() or []:
                    t, v = new.xref_get_key(annot.xref, "OC")
                    if t == "null":
                        continue
                    try:
                        layer_name = x2n.get(int(v.split()[0]))
                    except (ValueError, IndexError):
                        continue
                    if layer_name not in keep_layers:
                        doomed = annot
                        break
                if doomed is None:
                    break
                page.delete_annot(doomed)
    if target_name in n2x:
        on_x = [n2x[target_name]] + [n2x[n] for n in base_on]
        new.set_layer(-1, basestate="OFF", on=on_x)
    # else: unlayered source (labels path) -- nothing to switch off,
    # the page goes in whole with every subsystem's colors showing.
    out = output_path(plant, dtype, subsys)
    # Save to a temp file first, then swap into place: if the existing
    # output is open in a viewer (or locked by sync), the old file is
    # left intact and the caller gets a clean PermissionError to report.
    tmp = out + ".tmp"
    new.save(tmp, garbage=4, deflate=True)
    new.close()
    try:
        os.replace(tmp, out)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return out


def scan_plants(doc, file_plant):
    """Plant for every page: the most frequent plant code in the page's
    document numbers wins (title block beats stray codes in markup
    comments); ties are broken by the code's total mentions anywhere
    in the page text (every drawing references the common WFXX legend
    sheets, which can tie with the page's own number), then by the
    filename plant. Pages with no code inherit the nearest coded
    page's plant; anything still unknown falls back to the filename
    plant. Returns {page_number: plant_name}."""
    raw = {}
    for i in range(doc.page_count):
        txt = doc[i].get_text()
        counts = Counter(c for c in CODE_RE.findall(txt)
                         if config.plant_of_code(c))
        if counts:
            top = counts.most_common()
            best = top[0][1]
            tied = [c for c, n in top if n == best]
            if len(tied) == 1:
                raw[i + 1] = config.plant_of_code(tied[0])
                continue
            loose = Counter(c for c in LOOSE_RE.findall(txt)
                            if c in tied)
            if loose:
                ltop = loose.most_common()
                lbest = ltop[0][1]
                ltied = [c for c, n in ltop if n == lbest]
                if len(ltied) == 1:
                    raw[i + 1] = config.plant_of_code(ltied[0])
                    continue
                tied = ltied
            tied_plants = {config.plant_of_code(c) for c in tied}
            if file_plant in tied_plants:
                raw[i + 1] = file_plant
            else:
                raw[i + 1] = config.plant_of_code(tied[0])
            continue
        counts = Counter(c for c in LOOSE_RE.findall(txt)
                         if config.plant_of_code(c))
        if counts:
            raw[i + 1] = config.plant_of_code(counts.most_common(1)[0][0])
    plants = {}
    for pg in range(1, doc.page_count + 1):
        if pg in raw:
            plants[pg] = raw[pg]
            continue
        plant = None
        for p in list(range(pg - 1, 0, -1)) + list(range(pg + 1,
                                                       doc.page_count + 1)):
            if p in raw:
                plant = raw[p]
                break
        plants[pg] = plant or file_plant
    return plants


def process(path, wanted=None):
    parsed = parse_filename(path)
    if parsed:
        file_plant, dtype = parsed
    else:
        # Not a "Systemized" set name (e.g. Group1_Layered_Drawings.pdf):
        # treat as P&IDs and rely on document numbers for the plant.
        file_plant, dtype = None, "P&IDs"
        print(f"\n=== {os.path.basename(path)} -> name has no plant/type; "
              f"treating as P&IDs, plant from document numbers ===",
              flush=True)
    if parsed:
        print(f"\n=== {os.path.basename(path)} -> plant {file_plant}, "
              f"type {dtype} ===", flush=True)
    doc = pymupdf.open(path)
    ann_pages, _ = map_annotations(doc)
    cont_pages, _ = map_content(doc)
    if cont_pages:
        # SPPID/AutoCAD file: drawing-content layers rule. Any stray
        # review markups tagged to a layer are ignored for routing and
        # are never deleted from the outputs.
        mode = "content"
        subsys_pages = defaultdict(
            set, {k: set(v) for k, v in cont_pages.items()})
    elif ann_pages:
        # Bluebeam file: subsystem layers are markup annotations.
        mode = "annotations"
        subsys_pages = defaultdict(
            set, {k: set(v) for k, v in ann_pages.items()})
    else:
        # No subsystem layers of either kind: break labels only.
        mode = "content"
        subsys_pages = defaultdict(set)
    # Pages with NO subsystem layers at all (unlayered drawings, or a
    # mixed file where some pages were never marked up) fall back to
    # the break labels printed on the page. Label pages go in whole --
    # nothing to switch off or strip there.
    layered = set()
    for pages in subsys_pages.values():
        layered |= set(pages)
    label_map = map_labels(doc, layered)
    for k, v in label_map.items():
        subsys_pages[k] |= set(v)
    if not subsys_pages:
        print("  no subsystem layers or labels found (not marked up?) "
              "- skipped")
        doc.close()
        return 0, []
    n_subs = len(subsys_pages)
    n_label_pages = len(set().union(*label_map.values())) if label_map else 0
    print(f"  {n_subs} subsystems via {mode} layers"
          + (f" + {n_label_pages} pages via break labels"
             if n_label_pages else ""), flush=True)
    plants = scan_plants(doc, file_plant)
    doc.close()
    # group pages by (plant, subsystem)
    groups = defaultdict(list)
    dropped = 0
    for subsys, pages in subsys_pages.items():
        for p in pages:
            plant = plants.get(p)
            if not plant:
                dropped += 1
                continue
            groups[(plant, subsys)].append(p)
    if dropped:
        print(f"  WARNING: {dropped} pages had no determinable plant "
              f"and were skipped")
    plants_found = sorted({g[0] for g in groups})
    print(f"  plants: {', '.join(plants_found)}", flush=True)
    # save the maps for audit
    wdir = os.path.join(config.WORK_DIR,
                        os.path.splitext(os.path.basename(path))[0])
    os.makedirs(wdir, exist_ok=True)
    json.dump({k: sorted(v) for k, v in subsys_pages.items()},
              open(os.path.join(wdir, "layer_map.json"), "w"))
    json.dump({str(k): v for k, v in plants.items()},
              open(os.path.join(wdir, "page_plant.json"), "w"))
    todo = sorted(groups)
    if wanted:
        missing = [w for w in sorted(wanted)
                   if w not in {g[1] for g in groups}]
        for w in missing:
            print(f"  NOTE: {w} is not in this file - skipped here")
        todo = [g for g in todo if g[1] in wanted]
        if not todo:
            return 0, []
    count = 0
    failed = []
    for plant, subsys in todo:
        pages = sorted(groups[(plant, subsys)])
        try:
            out = build_one(path, plant, dtype, subsys, pages, mode)
        except Exception as e:
            # One bad output (usually the existing PDF is open in a
            # viewer, or OneDrive has it locked) must not kill the run.
            print(f"  !! SKIPPED {plant} {subsys}: {e}", flush=True)
            failed.append(subsys)
            continue
        print(f"  {plant} {subsys}: {len(pages)} pages -> "
              f"{os.path.basename(out)}", flush=True)
        count += 1
    if failed:
        print(f"  ** {len(failed)} subsystem(s) skipped for this file: "
              f"{', '.join(failed)} — close the output PDF if it is "
              f"open, then re-run just those numbers.", flush=True)
    return count, failed


def main():
    # Optional subsystem filter:  extract_all.py 33-05
    #                              extract_all.py 33-05 50-08 23-71
    #                              extract_all.py 33-05,50-08
    # No arguments = ALL subsystems.
    wanted = set()
    for arg in sys.argv[1:]:
        for piece in arg.replace(",", " ").split():
            wanted.add(piece)
    wanted = wanted or None
    if wanted:
        print(f"Subsystem filter: only {', '.join(sorted(wanted))}")
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    pdfs = sorted(glob.glob("*.pdf"))
    if not pdfs:
        print("No PDFs in this folder.")
        return 1
    total = 0
    all_failed = []
    for path in pdfs:
        n, failed = process(path, wanted)
        total += n
        all_failed += failed
    print(f"\nDONE: {total} files in {config.OUTPUT_DIR}/")
    if all_failed:
        print(f"SKIPPED (locked/open output PDFs): "
              f"{', '.join(sorted(set(all_failed)))} — close them and "
              f"re-run with just those numbers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
