# Isolate-Layers

Isolates systemized drawings by subsystem layers and extracts the pages for each subsystem into its own PDF.

`extract_all.py` reads every PDF in this folder. Bluebeam sets (subsystem layers stored as markup annotations) and SPPID/AutoCAD P&IDs (subsystem layers in the drawing content) are handled in one run. A page with no subsystem layers is filed from the subsystem numbers printed on the drawing. Original PDFs are left unchanged.

## Setup

Python 3 and [PyMuPDF](https://pypi.org/project/pymupdf/) are required.

```bash
python -m pip install -r requirements.txt
```

## Run

Put the drawings next to `extract_all.py`. Names like `WCF Systemized SLDs.pdf` supply the plant and document type (hyphens and underscores work too). Other names, such as `Group1_Layered_Drawings.pdf`, are treated as P&IDs and the plant is read from each page’s document number.

From this folder:

```bash
python extract_all.py
python extract_all.py 33-05
python extract_all.py 33-05 50-08 23-71
```

No arguments processes every subsystem found. Pass one or more `NN-NN` numbers to limit the run. A requested number that is not in a file is noted and skipped.

On Windows, `run_all.bat` asks for the same subsystem list and then calls `extract_all.py`.

## Output

Files are written under `output/`, grouped by plant, system (the first two digits), and subsystem:

```text
output/
  WCF/
    46/
      46-01/
        WCF 46-01 - Systemized PIDs (Layered).pdf
        WCF 46-01 - Systemized SLDs (Layered).pdf
```

Re-running updates those files in place. If an output PDF is open and cannot be replaced, that subsystem is skipped and listed at the end of the run. Close it and run again with just that number.

Audit maps for each source file are written under `work/`.
