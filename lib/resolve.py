"""Per-field waterfall, ordered by MEASURED accuracy, not by source reputation."""
import re,sys,os,json,subprocess
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from norm import edition, edition_from_comment

# field -> ordered source list. "pdf" and "local" are injected by the caller:
# "pdf" is what the file itself says, "local"/"local_note" a prior record you hold.
ORDER = {
 "title":      ["pdf","gb","crossref","openlibrary","k10plus","loc"],   # casing: catalogues are sentence-case
 "subtitle":   ["pdf","gb","k10plus","openlibrary","crossref"],
 "authors":    ["pdf","crossref","gb","k10plus","openlibrary","loc"],   # 91-100% pairwise order agreement
 "publisher":  ["crossref","k10plus","gb","openlibrary"],               # OL gives corporate parent, not imprint
 "year":       ["crossref","gb","openlibrary","pdf"],                   # NEVER k10plus: printing year, 37% wrong
 "edition":    ["pdf","local_note","k10plus","openlibrary","loc"],
 "series":     ["crossref","k10plus","local","openlibrary"],          # gb has none
 "series_no":  ["k10plus","local"],
 "place":      ["k10plus","openlibrary","loc"],                         # crossref/gb have none
 "language":   ["k10plus","gb","openlibrary","pdf"],
 "abstract":   ["gb","k10plus","crossref"],                             # gb 86% and they are real abstracts
 "pages":      ["mutool"],                                              # the file is the only truth
 "doi":        ["crossref"],
}
NEVER = {("year","k10plus"), ("pages","gb"), ("pages","openlibrary")}

def resolve(field, cand):
    """cand: {source: value}. Returns (value, source, agreement, conflicts)."""
    order=ORDER.get(field,[])
    vals={s:v for s,v in cand.items() if v not in (None,"",[]) and (field,s) not in NEVER}
    if not vals: return None,None,0,[]
    def norm(v):
        if isinstance(v,list): return tuple(re.sub(r"[^a-z]","",str(x).lower())[:14] for x in v)
        return re.sub(r"[^a-z0-9]","",str(v).lower())
    # MAJORITY FIRST, source priority only as the tie-break. Measured: three
    # sources agreeing beat one high-priority source (Cover & Thomas 2006 vs
    # Crossref's 2005; "Analysis I" vs Google Books' truncated "Analysis").
    groups={}
    for s,v in vals.items(): groups.setdefault(norm(v),[]).append(s)
    def rank(s): return order.index(s) if s in order else len(order)+1
    best=max(groups.values(), key=lambda ss:(len(ss), -min(rank(x) for x in ss)))
    src=min(best,key=rank); chosen=vals[src]
    agree=[s for s,v in vals.items() if norm(v)==norm(chosen)]
    conflict=[(s,v) for s,v in vals.items() if norm(v)!=norm(chosen)]
    return chosen, src, len(agree), conflict

def pdf_text(path,pages="1-6"):
    try:
        return subprocess.run(["mutool","draw","-F","txt","-o","-",path,pages],
            capture_output=True,timeout=90).stdout.decode("utf8","ignore")
    except Exception: return ""
def pdf_pages(path):
    try:
        out=subprocess.run(["mutool","info",path],capture_output=True,timeout=60).stdout.decode()
        m=re.search(r"^Pages:\s*(\d+)",out,re.M); return int(m.group(1)) if m else None
    except Exception: return None
