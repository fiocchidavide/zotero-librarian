# /// script
# requires-python = ">=3.10"
# dependencies = ["pymupdf"]
# ///
"""Evidence and mechanics for rebuilding a missing PDF outline (bookmarks).

Nothing here decides what the outline says. The model reads the printed TOC AND
the headings actually typeset in the body, curates a spec (titles cleaned up,
sections the printed TOC omits added), and checks the rendered result by eye.

Spec: one entry per line, tab-separated, `#` comments allowed.
    level <TAB> page <TAB> title
`page` is the PRINTED page number; `=N` is an absolute PDF page (1-based), for
front matter in roman and back matter the printed TOC leaves out.

    uv run outline.py headings <pdf>                 bold/large lines, per page, with y
    uv run outline.py check <pdf> <spec> [--offset N]
    uv run outline.py write <pdf> <spec> <out.pdf> [--offset N] [--labels 1:r,7:D]
                            [--title T] [--author A] [--force] [--replace]
    uv run outline.py verify <pdf> <sheet.png>       read back + contact sheet of every target

check prints, per entry, how the page's own heading compares with the spec title:
`ok` same words, `~` similar (the page text is shown: decide whether your title or
the transcription is right), `text` title only in running text (bookmark points at
page top), `MISS` not on that page. write points each bookmark just above the
matched heading, so mid-page sections land on the heading, not the page top.
"""
import difflib,re,sys,unicodedata
import pymupdf

def norm(s):
    """Letters and digits only. Survives casing, dashes, curly quotes, line
    wraps, and the `Schr¨odinger` that TeX accent extraction produces."""
    s=unicodedata.normalize("NFKD",s)
    return re.sub(r"[^a-z0-9]","","".join(c for c in s if not unicodedata.combining(c)).lower())

def key(title):
    """The title without its section number."""
    return norm(re.sub(r"^\s*(appendix\s+[a-z]\b|\d+(\.\d+)*)\s*[-–—.:]?\s*","",title,flags=re.I)) or norm(title)

def _line_text(line):
    """TeX PDFs often have no space glyphs; put spaces back from the gaps."""
    out,prev=[],None
    for s in line["spans"]:
        for c in s["chars"]:
            if prev and c["bbox"][0]-prev["bbox"][2]>0.18*s["size"] and not c["c"].isspace() and out and out[-1]!=" ": out.append(" ")
            out.append(c["c"]); prev=c
    return re.sub(r"\s+"," ","".join(out)).strip()

def _bold(f): return bool(re.search(r"bold|black|heavy|semibold|BX|-B\b|\.B\b",f,re.I))

def headings(doc):
    """Lines set entirely in a bold face, merged when they share a baseline
    (TeX sets the section number and title as separate lines). Evidence only:
    inline bold formulas show up too, and unbolded headings won't."""
    res=[]
    for pno,page in enumerate(doc,1):
        rows=[]
        for b in page.get_text("rawdict")["blocks"]:
            for l in b.get("lines",[]):
                sp=[s for s in l["spans"] if "".join(c["c"] for c in s["chars"]).strip()]
                if not sp or not all(_bold(s["font"]) for s in sp): continue
                rows.append([l["bbox"][1],l["bbox"][0],max(s["size"] for s in sp),_line_text(l)])
        rows.sort()
        merged=[]
        for r in rows:
            if merged and abs(merged[-1][0]-r[0])<2 and abs(merged[-1][2]-r[2])<.5: merged[-1][3]+=" "+r[3]
            else: merged.append(r)
        res+= [(pno,y,size,t) for y,_,size,t in merged]
    return res

def parse_spec(path):
    out=[]
    for ln in open(path,encoding="utf8"):
        if not ln.strip() or ln.lstrip().startswith("#"): continue
        lvl,pg,title=ln.rstrip("\n").split("\t",2)
        out.append((int(lvl),pg.strip(),title.strip()))
    return out

def resolve(spec,offset):
    return [(l,t,int(p[1:]) if p.startswith("=") else int(p)+offset) for l,p,t in spec]

def find_offset(spec,texts):
    """The offset under which the most entries land on a page containing their
    title. Every entry votes, so one odd heading can't skew it."""
    score=lambda o:sum(0<p<=len(texts) and key(t)[:30] in texts[p-1] for _,t,p in resolve(spec,o))
    return max(range(-len(texts),len(texts)),key=score)

def match(entries,doc,heads):
    """Per entry: (status, y of the matched heading or None, page's own text)."""
    texts=[norm(p.get_text()) for p in doc]
    out=[]
    for _,t,p in entries:
        if not 0<p<=len(texts): out.append(("MISS",None,"page out of range")); continue
        cands=[(difflib.SequenceMatcher(None,key(t),key(h)).ratio(),y,h) for q,y,_,h in heads if q==p]
        r,y,h=max(cands,default=(0,None,""))
        if r>=.95: out.append(("ok",y,h))
        elif r>=.6: out.append(("~",y,h))
        elif key(t)[:30] in texts[p-1]: out.append(("text",None,""))
        else: out.append(("MISS",None,""))
    return out

def check(doc,spec,offset=None):
    if offset is None: offset=find_offset(spec,[norm(p.get_text()) for p in doc])
    entries=resolve(spec,offset)
    return offset,entries,match(entries,doc,headings(doc))

def report(offset,entries,m):
    print(f"offset: printed page + {offset} = PDF page")
    for (l,t,p),(st,y,h) in zip(entries,m):
        print(f"{st:<4} p{p:<4} {'  '*(l-1)}{t}"+(f"   ← page says: {h}" if st=="~" else ""))
    print(f"{sum(s=='ok' for s,_,_ in m)}/{len(m)} exact; review every other line")

def parse_labels(s):
    """'1:r,7:D' -> roman from PDF page 1, arabic from page 7 (restarting at 1).
    Styles: D r R a A; append =N to start at N, e.g. '7:D=3'."""
    out=[]
    for part in s.split(","):
        pg,st=part.split(":"); st,_,first=st.partition("=")
        out.append({"startpage":int(pg)-1,"prefix":"","style":st,"firstpagenum":int(first or 1)})
    return out

def write(pdf,spec,out,offset=None,force=False,replace=False,labels=None,title=None,author=None):
    doc=pymupdf.open(pdf)
    if doc.get_toc() and not replace: sys.exit("PDF already has an outline; pass --replace")
    offset,entries,m=check(doc,spec,offset)
    report(offset,entries,m)
    if any(s=="MISS" for s,_,_ in m) and not force: sys.exit("not written: resolve the MISS lines, or --force once you've looked at those pages")
    levels=[l for l,_,_ in entries]
    if levels[0]!=1 or any(b>a+1 for a,b in zip(levels,levels[1:])): sys.exit("levels must start at 1 and step down by one")
    toc=[]
    for (l,t,p),(_,y,_) in zip(entries,m):
        to=pymupdf.Point(0,max(0,y-12)) if y is not None else pymupdf.Point(0,0)
        toc.append([l,t,p,{"kind":pymupdf.LINK_GOTO,"page":p-1,"to":to,"zoom":0}])
    doc.set_toc(toc,collapse=1)
    if labels: doc.set_page_labels(parse_labels(labels))
    meta=doc.metadata
    if title: meta["title"]=title
    if author: meta["author"]=author
    doc.set_metadata(meta)
    doc.save(out,garbage=1,deflate=True)
    n=len(pymupdf.open(out).get_toc())
    print(f"wrote {out}: {n} outline entries")
    if n!=len(entries): sys.exit(f"expected {len(entries)} entries, read back {n}")

def verify(pdf,sheet,band=70,width=420):
    """Read the outline back from the written file and render, for every entry,
    the strip of page each bookmark lands on. Look at the sheet: the heading
    should sit at the top of every strip."""
    doc=pymupdf.open(pdf)
    toc=doc.get_toc(simple=False)
    for l,t,p,d in toc:
        print(f"p{p:<4} [{doc[p-1].get_label() or '-'}] y={d.get('to',pymupdf.Point(0,0)).y:6.1f} {'  '*(l-1)}{t}")
    cols,lab=2,16
    rows=(len(toc)+cols-1)//cols
    out=pymupdf.open(); sp=out.new_page(width=cols*width,height=rows*(band+lab))
    for i,(l,t,p,d) in enumerate(toc):
        pg=doc[p-1]; y=d.get("to",pymupdf.Point(0,0)).y
        x0,y0=(i%cols)*width,(i//cols)*(band+lab)
        sp.insert_text((x0+4,y0+12),f"{'  '*(l-1)}{t}  [p.{pg.get_label() or p}]",fontsize=9,color=(.75,0,0))
        clip=pymupdf.Rect(0,y,pg.rect.width,min(pg.rect.height,y+band*pg.rect.width/width))
        sp.show_pdf_page(pymupdf.Rect(x0,y0+lab,x0+width-6,y0+lab+band),doc,p-1,clip=clip)
        sp.draw_rect(pymupdf.Rect(x0,y0+lab,x0+width-6,y0+lab+band),color=(.7,.7,.7),width=.5)
    sp.get_pixmap(dpi=110).save(sheet)
    print(f"contact sheet: {sheet} | page labels: {doc[0].get_label() or 'none'} … {doc[-1].get_label() or 'none'} | title: {doc.metadata.get('title')!r}")

if __name__=="__main__":
    a=sys.argv[1:]
    flag=lambda f:f in a and not a.remove(f)
    def opt(f,conv=str):
        if f not in a: return None
        i=a.index(f); v=a[i+1]; del a[i:i+2]; return conv(v)
    force,replace=flag("--force"),flag("--replace")
    off,labels,title,author=opt("--offset",int),opt("--labels"),opt("--title"),opt("--author")
    if a[:1]==["headings"] and len(a)==2:
        for p,y,s,t in headings(pymupdf.open(a[1])): print(f"p{p:<4} y={y:6.1f} {s:4.1f}pt  {t}")
    elif a[:1]==["check"] and len(a)==3: report(*check(pymupdf.open(a[1]),parse_spec(a[2]),off))
    elif a[:1]==["write"] and len(a)==4: write(a[1],parse_spec(a[2]),a[3],off,force,replace,labels,title,author)
    elif a[:1]==["verify"] and len(a)==3: verify(a[1],a[2])
    else: sys.exit(__doc__)
