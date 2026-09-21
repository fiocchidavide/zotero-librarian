"""Front matter extraction for adjudication (PLAN.md 2.6).

The model reads what this produces. It deliberately does NOT try to parse a
title out of the pages -- that judgement is the model's.
"""
import os,re,subprocess

def _run(a,timeout=120):
    try: return subprocess.run(a,capture_output=True,timeout=timeout).stdout
    except Exception: return b""

def page_text(pdf,rng="1-10"):
    return _run(["mutool","draw","-F","txt","-o","-",pdf,rng]).decode("utf8","ignore")

def page_geometry(pdf,rng="1-10"):
    """Page sizes, in points. A cover pasted in from elsewhere usually differs
    in size or aspect from the body it was glued onto."""
    out=_run(["mutool","pages",pdf,rng]).decode("utf8","ignore")
    g=[]
    for m in re.finditer(r'<page pagenum="(\d+)".*?<MediaBox l="([\d.-]+)" b="([\d.-]+)"'
                         r' r="([\d.-]+)" t="([\d.-]+)"',out,re.S):
        n,x0,y0,x1,y1=m.groups()
        w,h=abs(float(x1)-float(x0)),abs(float(y1)-float(y0))
        g.append({"page":int(n),"w":round(w,1),"h":round(h,1),
                  "aspect":round(w/h,3) if h else None})
    return g

def render(pdf,outdir,rng="1-10",dpi=150):
    """Render front matter to PNGs the model can look at. Cheap even on huge
    scans: page 3 of a 206 MB file renders in ~0.03 s."""
    os.makedirs(outdir,exist_ok=True)
    _run(["mutool","draw","-F","png","-r",str(dpi),
          "-o",os.path.join(outdir,"p%d.png"),pdf,rng],timeout=600)
    return sorted(os.path.join(outdir,f) for f in os.listdir(outdir) if f.endswith(".png"))

def cover_suspicion(pdf):
    """Reasons to distrust page 1. Signals only -- the model decides.
    47% of the migrated corpus had an image-only first page."""
    why=[]
    # NB: an aggregator watermark is often part of the cover IMAGE and therefore
    # invisible to text extraction -- #201 carried "http://freepdf-books.com"
    # and only the geometry check flagged it. Looking at the page is what finds
    # these; the signals below just decide which pages to look at first.
    t1=page_text(pdf,"1").strip()
    trest=page_text(pdf,"2-8").strip()
    if len(t1)<40:
        why.append("page 1 has no usable text layer (image-only cover)")
        if len(trest)>200:
            why.append("...while the body does have a text layer -- different provenance")
    g=page_geometry(pdf,"1-8")
    if len(g)>2:
        a0=g[0]["aspect"]; rest=[p["aspect"] for p in g[1:] if p["aspect"]]
        if a0 and rest:
            med=sorted(rest)[len(rest)//2]
            if abs(a0-med)>0.03:
                why.append(f"page 1 aspect {a0} differs from the body's {med}")
    if re.search(r"(libgen|z-?lib|book4you|annas?-archive|scribd|amazon|freepdf|"
                 r"pdfdrive|ebook3000|it-ebooks|foxgreat|https?://|www\.)",t1,re.I):
        why.append("page 1 carries retailer/aggregator text or a URL")
    return why

def needs_visual_read(pdf):
    """True when the text layer is not enough and the pages must be looked at."""
    return len(page_text(pdf,"1-8").strip())<200
