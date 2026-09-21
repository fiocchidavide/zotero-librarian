import re
ORD={"first":1,"second":2,"third":3,"fourth":4,"fifth":5,"sixth":6,"seventh":7,"eighth":8,
     "ninth":9,"tenth":10,"eleventh":11,"twelfth":12,
     "prima":1,"seconda":2,"terza":3,"quarta":4,"quinta":5,"sesta":6,
     "erste":1,"zweite":2,"dritte":3,"vierte":4,"fuenfte":5}
EDWORD=r"(?:ed\b|edition|edizione|ediz|auflage|aufl|ausg)"
# a clause that only describes a PRINTING is not an edition
NOISE=re.compile(r"\b(print(ing|ed|\.|s)?|pr\.|nachdr|repr|reprint|ristampa)\b",re.I)
# an edition named for an occasion is not a numbered edition
OCCASION=re.compile(r"\b(anniversary|jubil|commemorat)\w*",re.I)
# qualifiers allowed to sit between the ordinal and the word "edition"
QUAL=r"(?:[\w.&'-]+\s+){0,3}"

def edition(s):
    """(number|None, raw|None). A printing is never an edition; an
    anniversary/commemorative edition is not a NUMBERED edition."""
    if not s: return None,None
    s=str(s).strip()
    for clause in re.split(r"[,;]",s):
        c=clause.strip().strip("[]() ")
        if not c: continue
        has_edword=re.search(EDWORD,c,re.I)
        if NOISE.search(c) and not has_edword: continue      # pure printing
        if OCCASION.search(c): return None,c                  # keep text, no number
        m=re.search(rf"(\d+)\s*(?:st|nd|rd|th|a|\.)?\s*[-\s]?{QUAL}{EDWORD}",c,re.I)
        if m: return int(m.group(1)),c
        ORDALT="|".join(ORD)
        m=re.search(rf"\b({ORDALT})\s+{QUAL}{EDWORD}",c,re.I)
        if m: return ORD[m.group(1).lower()],c
    return None,None

CAL_ORD="|".join(ORD)
def edition_from_comment(s):
    if not s: return None
    if OCCASION.search(s): return None
    m=re.search(rf"\b({CAL_ORD})\s+(?:edition|edizione)\b",s,re.I)
    if m: return ORD.get(m.group(1).lower())
    m=re.search(r"\b(\d+)\s*(?:st|nd|rd|th|a)?\s*(?:ed\b|edition|edizione)",s,re.I)
    if m: return int(m.group(1))
    return None
