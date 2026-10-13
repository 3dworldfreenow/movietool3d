"""🛡 A small bad-word filter for what people type that others see: walker names, chat, news, story text.

It masks whole words (and the usual tricks: l33t letters, repeated letters, dots or spaces inside a word) with ✱ - it
does not try to understand meaning. English + common Hindi / Hinglish insults. Keep the list short and obvious: a
filter that blocks innocent words ("Scunthorpe") is worse than one that misses a rare insult; the 🚩 report button
catches the rest.
"""
import re

_WORDS = {
    # English
    "fuck", "fucker", "fucking", "motherfucker", "shit", "bullshit", "bitch", "bastard", "asshole", "dick", "dickhead",
    "cunt", "slut", "whore", "fag", "faggot", "nigger", "nigga", "retard", "wanker", "twat", "prick", "pussy", "cock",
    "rape", "rapist", "porn", "nazi",
    # Hindi / Hinglish
    "chutiya", "chutiye", "chootiya", "chutia", "chut", "madarchod", "maderchod", "behenchod", "bhenchod", "bhosdike", "bhosdi", "bhosda",
    "gandu", "gaandu", "randi", "harami", "haramkhor", "lund", "lauda", "lavda", "loda", "jhaat", "kutta", "kamina",
    "kutiya", "saala", "suar", "mc", "bc", "bsdk",
}
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "!": "i", "|": "i"})


def _norm(w):
    w = w.lower().translate(_LEET)
    w = re.sub(r"[^a-z]", "", w)
    return re.sub(r"(.)\1{2,}", r"\1\1", w)                       # fuuuuck -> fuuck


def _bad(w):
    n = _norm(w)
    if not n:
        return False
    if n in _WORDS or re.sub(r"(.)\1+", r"\1", n) in _WORDS:     # (also with every doubled letter made single)
        return True
    return any(n.startswith(b) and len(b) >= 5 for b in _WORDS)  # fuckers, chutiyapa ...


def clean(text, n=300):
    """the text with bad words masked (✱✱✱); also joins words split with dots / spaces (f.u.c.k, f u c k)"""
    s = " ".join(str(text or "").split())[:n]
    joined = re.sub(r"\b(?:\w[.\-_ ]){2,}\w\b", lambda m: m.group(0) if not _bad(re.sub(r"[.\-_ ]", "", m.group(0))) else "✱" * 4, s)
    return re.sub(r"[\w@$!|]+", lambda m: "✱" * len(m.group(0)) if _bad(m.group(0)) else m.group(0), joined)


def is_bad(text):
    return clean(text) != " ".join(str(text or "").split())
