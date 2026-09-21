"""Cleanup rules, each one traceable to a defect observed on the real corpus."""
import html,re,unicodedata

# D2: Crossref returns XML-escaped text  ("Measure, Integration &amp; Real Analysis")
def unescape(s): return html.unescape(s) if isinstance(s,str) else s

# D1: Google Books splits the subtitle into its own field
def join_subtitle(title, subtitle):
    if not title: return title
    if subtitle and subtitle.lower() not in title.lower():
        return f"{title.rstrip(' :')}: {subtitle}"
    return title

# D6: Google Books appends the edition to the title
#     ("Introduction to Algorithms, fourth edition")
EDTAIL=re.compile(r"[,:;]\s*(?:the\s+)?(?:[a-z]+|\d+(?:st|nd|rd|th))[-\s]?(?:revised\s+|updated\s+)?"
                  r"(?:edition|ed\.?)\s*$",re.I)
def strip_edition_tail(t):
    return EDTAIL.sub("",t).strip() if t else t

# D3: catalogue records are sentence-case; Zotero/CSL want the title as printed
def is_sentence_case(t):
    w=[x for x in re.findall(r"[A-Za-z]{4,}",t or "")]
    if len(w)<3: return False
    return sum(1 for x in w if x[0].isupper())/len(w) < 0.6

# D5: k10plus puts platform names in the series field
SERIES_JUNK={"springerlink","springer ebook collection","springer ebooks","ebook collection",
             "elibrary","oreilly","safari books online","wiley online library","sciencedirect",
             "acm digital library","ieee xplore","taylor & francis ebooks",
             "always learning","pearson","springer eBook Collection".lower()}
def clean_series(s):
    if not s: return None
    s=unescape(s).strip(" /:,;.")
    return None if s.lower() in SERIES_JUNK else s

# D8: MARC place artefacts  ("New York [u.a.]", "Upper Saddle River, NJ [u.a.]")
def clean_place(p):
    if not p: return None
    p=re.sub(r"\[.*?\]","",p).strip(" ,;:/[]")
    p=re.sub(r"\s*\bu\.\s*a\.?\s*$","",p,flags=re.I).strip(" ,")
    return p or None

# D7: creator names arrive in three shapes; Zotero wants {firstName, lastName}
PARTICLES={"van","von","de","der","den","del","della","di","da","le","la","du","ten","ter","dos","al"}
def split_name(n):
    n=unescape(str(n)).strip()
    n=re.sub(r"\s*\(.*?\)\s*|\s*\d{4}\s*-\s*\d{0,4}\s*","",n).strip(" ,.")
    if "," in n:
        last,first=[x.strip() for x in n.split(",",1)]
        # inverted form parks the particle at the end: "Oorschot, Paul C. van"
        fp=first.split()
        while fp and fp[-1].lower().strip(".") in PARTICLES:
            last=fp.pop()+" "+last
        return " ".join(fp),last
    parts=n.split()
    if len(parts)==1: return "",parts[0]
    i=len(parts)-1
    while i>0 and parts[i-1].lower().strip(".") in PARTICLES: i-=1
    return " ".join(parts[:i])," ".join(parts[i:])

# D4: the copyright page is the PDF's own claim about the year
COPY=re.compile(r"(?:©|\(c\)|copyright)\s*(?:by\s+)?([^A-Za-z]{0,60})",re.I)
YR=re.compile(r"\b(19|20)(\d{2})\b")
def year_from_pdf(text):
    """A copyright line may list every edition: '© 1996, 2005, 2024'. The
    latest year in the line is the one that dates THIS printing."""
    yrs=[]
    for tail in COPY.findall(text or ""):
        yrs += [int(a+b) for a,b in YR.findall(tail)]
    yrs=[y for y in yrs if 1900<=y<=2027]
    return str(max(yrs)) if yrs else None
