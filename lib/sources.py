import json,os,re,sys,time,urllib.request,urllib.parse
import xml.etree.ElementTree as ET
CACHE=os.path.join(os.environ.get("SCR", os.path.expanduser("~/.cache/zotero-librarian")), "cache")
os.makedirs(CACHE, exist_ok=True)
MAILTO="davidefiocchi2@gmail.com"
GB_KEY=os.environ.get("GB_KEY","")

def fetch(url,key,binary=False,timeout=30):
    p=os.path.join(CACHE,key.replace("/","_")+".raw")
    if os.path.exists(p): return open(p,"rb").read()
    os.makedirs(CACHE, exist_ok=True)
    try:
        req=urllib.request.Request(url,headers={"User-Agent":f"zotero-librarian/1.0 (mailto:{MAILTO})"})
        b=urllib.request.urlopen(req,timeout=timeout).read()
    except Exception as e:
        b=b""
    open(p,"wb").write(b); time.sleep(0.15); return b

def blank():
    return dict(hit=False,title=None,subtitle=None,authors=[],publisher=None,year=None,
                edition=None,series=None,series_no=None,pages=None,place=None,
                language=None,abstract=False,doi=None)

# ---------------- Google Books ----------------
def gb(isbn):
    r=blank()
    b=fetch(f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}&key={GB_KEY}",f"gb_{isbn}")
    try: d=json.loads(b)
    except: return r
    if d.get("error") or not d.get("totalItems"): return r
    v=d["items"][0]["volumeInfo"]; r["hit"]=True
    r["title"]=v.get("title"); r["subtitle"]=v.get("subtitle")
    r["authors"]=v.get("authors",[])
    r["publisher"]=v.get("publisher")
    pd=v.get("publishedDate") or ""
    r["year"]=pd[:4] if pd else None
    r["pages"]=v.get("pageCount")
    r["language"]=v.get("language")
    r["abstract"]=bool(v.get("description"))
    return r

# ---------------- Crossref ----------------
BOOKTYPES={"book","monograph","reference-book","edited-book"}
def cr(isbn):
    r=blank()
    b=fetch(f"https://api.crossref.org/works?filter=isbn:{isbn},type:book&rows=1&mailto={MAILTO}",f"cr_{isbn}")
    it=None
    try:
        d=json.loads(b)["message"]
        if d["total-results"]: it=d["items"][0]
    except: pass
    if it is None:
        b=fetch(f"https://api.crossref.org/works?filter=isbn:{isbn}&rows=1&mailto={MAILTO}",f"cra_{isbn}")
        try:
            d=json.loads(b)["message"]
            if d["total-results"]:
                doi=d["items"][0]["DOI"]
                base=doi.rsplit("_",1)[0] if "_" in doi else doi.rsplit(".",1)[0]
                b2=fetch(f"https://api.crossref.org/works/{urllib.parse.quote(base)}?mailto={MAILTO}",f"crb_{isbn}")
                m=json.loads(b2)["message"]
                if m.get("type") in BOOKTYPES: it=m
        except: pass
    if it is None: return r
    r["hit"]=True
    t=it.get("title") or [None]; r["title"]=t[0]
    st=it.get("subtitle") or []; r["subtitle"]=st[0] if st else None
    r["authors"]=[f"{a.get('family','')}, {a.get('given','')}".strip(", ") for a in it.get("author",[])]
    r["publisher"]=it.get("publisher")
    dp=it.get("issued",{}).get("date-parts") or [[None]]
    r["year"]=str(dp[0][0]) if dp[0][0] else None
    ct=it.get("container-title") or []; r["series"]=ct[0] if ct else None
    r["edition"]=it.get("edition-number")
    r["doi"]=it.get("DOI")
    r["abstract"]=bool(it.get("abstract"))
    return r

# ---------------- Open Library ----------------
def ol(isbn):
    r=blank()
    b=fetch(f"https://openlibrary.org/isbn/{isbn}.json",f"ol_{isbn}")
    try: d=json.loads(b)
    except: return r
    if not isinstance(d,dict) or "title" not in d: return r
    r["hit"]=True
    r["title"]=d.get("title"); r["subtitle"]=d.get("subtitle")
    r["publisher"]=(d.get("publishers") or [None])[0]
    pd=d.get("publish_date") or ""
    m=re.search(r"(\d{4})",pd); r["year"]=m.group(1) if m else None
    r["edition"]=d.get("edition_name")
    s=d.get("series") or []; r["series"]=s[0] if s else None
    r["pages"]=d.get("number_of_pages")
    r["place"]=(d.get("publish_places") or [None])[0]
    lg=d.get("languages") or []
    r["language"]=lg[0]["key"].split("/")[-1] if lg else None
    r["abstract"]=bool(d.get("description"))
    names=[]
    for a in d.get("authors",[])[:8]:
        ab=fetch(f"https://openlibrary.org{a['key']}.json",f"ola_{a['key'].split('/')[-1]}")
        try: names.append(json.loads(ab).get("name"))
        except: pass
    r["authors"]=[n for n in names if n]
    return r

# ---------------- K10plus (MARCXML) ----------------
MARC="{http://www.loc.gov/MARC21/slim}"
def _sf(f,code):
    for s in f.findall(f"{MARC}subfield"):
        if s.get("code")==code: return (s.text or "").strip(" /:,;.")
    return None
def k10(isbn):
    r=blank()
    b=fetch("https://sru.k10plus.de/opac-de-627?version=1.1&operation=searchRetrieve"
            f"&query=pica.isb%3D{isbn}&maximumRecords=1&recordSchema=marcxml",f"k10_{isbn}")
    try: root=ET.fromstring(b)
    except: return r
    rec=root.find(f".//{MARC}record")
    if rec is None: return r
    r["hit"]=True
    F={}
    for f in rec.findall(f"{MARC}datafield"): F.setdefault(f.get("tag"),[]).append(f)
    if "245" in F:
        r["title"]=_sf(F["245"][0],"a"); r["subtitle"]=_sf(F["245"][0],"b")
    if "250" in F: r["edition"]=_sf(F["250"][0],"a")
    for t in ("264","260"):
        if t in F:
            r["place"]=r["place"] or _sf(F[t][0],"a")
            r["publisher"]=r["publisher"] or _sf(F[t][0],"b")
            d=_sf(F[t][0],"c") or ""
            m=re.search(r"(\d{4})",d)
            if m and not r["year"]: r["year"]=m.group(1)
    if "300" in F:
        e=_sf(F["300"][0],"a") or ""
        m=re.search(r"(\d+)\s*(?:S\.|p|pages)",e)
        if m: r["pages"]=int(m.group(1))
    for t in ("830","490"):
        if t in F and not r["series"]:
            r["series"]=_sf(F[t][0],"a"); r["series_no"]=_sf(F[t][0],"v")
    au=[]
    for t in ("100","700"):
        for f in F.get(t,[]):
            n=_sf(f,"a")
            if n and n not in au: au.append(n)
    r["authors"]=au
    if "041" in F: r["language"]=_sf(F["041"][0],"a")
    if "520" in F: r["abstract"]=True
    return r

# ---------------- Library of Congress (MODS) ----------------
MODS="{http://www.loc.gov/mods/v3}"
def loc(isbn):
    r=blank()
    b=fetch("http://lx2.loc.gov:210/LCDB?version=1.1&operation=searchRetrieve"
            f"&query=bath.isbn={isbn}&maximumRecords=1&recordSchema=mods",f"loc_{isbn}",timeout=40)
    try: root=ET.fromstring(b)
    except: return r
    m=root.find(f".//{MODS}mods")
    if m is None: return r
    r["hit"]=True
    ti=m.find(f"{MODS}titleInfo")
    if ti is not None:
        t=ti.find(f"{MODS}title"); st=ti.find(f"{MODS}subTitle")
        r["title"]=t.text if t is not None else None
        r["subtitle"]=st.text if st is not None else None
    au=[]
    for n in m.findall(f"{MODS}name"):
        if n.get("type")!="personal": continue
        roles=[x.text for x in n.findall(f"{MODS}role/{MODS}roleTerm")]
        if roles and not any(x in ("author","creator") for x in roles if x): continue
        np=n.find(f"{MODS}namePart")
        if np is not None and np.text: au.append(np.text.strip(" ,."))
    r["authors"]=au
    oi=m.find(f"{MODS}originInfo")
    if oi is not None:
        p=oi.find(f"{MODS}publisher"); r["publisher"]=p.text if p is not None else None
        for pl in oi.findall(f"{MODS}place/{MODS}placeTerm"):
            if pl.get("type")=="text": r["place"]=pl.text; break
        for d in oi.findall(f"{MODS}dateIssued"):
            mm=re.search(r"(\d{4})",d.text or "")
            if mm: r["year"]=mm.group(1); break
        e=oi.find(f"{MODS}edition"); r["edition"]=e.text if e is not None else None
    ex=m.find(f"{MODS}physicalDescription/{MODS}extent")
    if ex is not None and ex.text:
        mm=re.search(r"(\d+)\s*p",ex.text)
        if mm: r["pages"]=int(mm.group(1))
    for ri in m.findall(f"{MODS}relatedItem"):
        if ri.get("type")=="series":
            t=ri.find(f"{MODS}titleInfo/{MODS}title")
            if t is not None: r["series"]=t.text; break
    lt=m.find(f"{MODS}language/{MODS}languageTerm")
    if lt is not None: r["language"]=lt.text
    if m.find(f"{MODS}abstract") is not None: r["abstract"]=True
    return r

SOURCES={"gb":gb,"crossref":cr,"openlibrary":ol,"k10plus":k10,"loc":loc}
