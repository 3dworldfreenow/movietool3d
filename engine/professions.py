"""Professions: one word -> outfit, hat, hand tool, glasses/beard hints and usual workplace.

JSON:  "raju": {"name": "Raju", "profession": "police"}
Anything you also set on the character (colours, gender, hat...) overrides the profession default.
"""

PROFESSIONS = {
    "doctor":      dict(outfit="labcoat", pants="#4a5568", tool="stethoscope", workplace="hospital", glasses=None),
    "nurse":       dict(outfit="nurse", hat="nurse", gender="female", tool="clipboard", workplace="hospital_room"),
    "police":      dict(outfit="police", hat="police", tool="baton", mustache=True, workplace="police_station"),
    "soldier":     dict(outfit="army", hat="beret", accent="#3d4f2a", tool=None, workplace="road"),
    "firefighter": dict(outfit="firefighter", hat="fire_helmet", accent="#c1121f", tool="axe", workplace="street"),
    "teacher":     dict(outfit="salwar", tool="book", glasses=True, workplace="classroom"),
    "student":     dict(outfit="uniform", age="child", tool="bag", workplace="school_ground"),
    "farmer":      dict(outfit="farmer", hat="turban", accent="#e9c46a", tool="sickle", workplace="farm"),
    "shopkeeper":  dict(outfit="kurta", outfit_color="#e9c46a", tool="scale", workplace="market", build="chubby"),
    "chef":        dict(outfit="chef", hat="chef", tool="ladle", workplace="kitchen"),
    "postman":     dict(outfit="police", outfit_color="#b08d57", hat="cap", accent="#8b6b3d", tool="letters", workplace="street"),
    "driver":      dict(outfit="shirt", outfit_color="#f1faee", pants="#2f3e55", hat="cap", accent="#1d3557", tool=None, workplace="road"),
    "pilot":       dict(outfit="pilot", hat="pilot", accent="#1d3557", tool=None, workplace="road"),
    "astronaut":   dict(outfit="astronaut", tool=None, workplace="space"),
    "engineer":    dict(outfit="overalls", hat="hard_hat", accent="#f4c430", tool="wrench", workplace="road"),
    "mechanic":    dict(outfit="overalls", tool="wrench", workplace="street"),
    "scientist":   dict(outfit="labcoat", glasses=True, tool="test_tube", workplace="office"),
    "painter":     dict(outfit="tshirt", outfit_color="#f1faee", hat="beret", accent="#e63946", tool="brush", workplace="room"),
    "musician":    dict(outfit="kurta", outfit_color="#6a4c93", tool="flute", workplace="temple_fair"),
    "king":        dict(outfit="royal", hat="crown", accent="#b8860b", outfit_color="#7b2cbf", tool="scepter", mustache=True, workplace="palace"),
    "queen":       dict(outfit="saree", hat="crown", accent="#d4a017", outfit_color="#9d0208", gender="female", tool=None, workplace="palace"),
    "prince":      dict(outfit="royal", hat="crown", accent="#d4a017", outfit_color="#1d4e89", tool="sword", workplace="palace"),
    "princess":    dict(outfit="dress", hat="crown", accent="#d4a017", outfit_color="#ff70a6", gender="female", workplace="palace"),
    "sadhu":       dict(outfit="sadhu", hair="bun", beard=True, age="old", tool="staff", workplace="temple_fair"),
    "cricketer":   dict(outfit="sports", outfit_color="#1d4ed8", hat="cap", accent="#1d4ed8", tool="bat", workplace="cricket_ground"),
    "officer":     dict(outfit="suit", accent="#c1121f", tool="briefcase", workplace="office"),
    "grandmother": dict(outfit="saree", gender="female", age="old", hair="bun", glasses=True, outfit_color="#f1faee", accent="#9d0208", workplace="room"),
    "grandfather": dict(outfit="kurta", age="old", glasses=True, tool="walking_stick", workplace="village"),
    "waiter":      dict(outfit="suit", outfit_color="#ffffff", pants="#111111", tool="tray", workplace="restaurant"),
}
ALIASES = {"cop": "police", "policeman": "police", "inspector": "police", "army": "soldier", "fireman": "firefighter",
           "sir": "teacher", "madam": "teacher", "kid": "student", "kisan": "farmer", "cook": "chef",
           "raja": "king", "rani": "queen", "rajkumar": "prince", "rajkumari": "princess", "saint": "sadhu",
           "baba": "sadhu", "dadi": "grandmother", "nani": "grandmother", "dadaji": "grandfather",
           "nanaji": "grandfather", "boss": "officer", "businessman": "officer", "clerk": "officer",
           "shop_owner": "shopkeeper", "vendor": "shopkeeper", "dhabawala": "chef", "cyclist": "student"}


def resolve(name):
    key = str(name or "").lower().strip().replace(" ", "_")
    key = ALIASES.get(key, key)
    return key if key in PROFESSIONS else None


def apply(spec):
    """Return a new spec with profession defaults filled in (explicit keys win)."""
    prof = resolve(spec.get("profession"))
    if not prof:
        return spec
    base = {k: v for k, v in PROFESSIONS[prof].items() if v is not None and k != "workplace"}
    out = dict(base)
    out.update(spec)
    out["profession"] = prof
    return out


def workplace(name):
    p = resolve(name)
    return PROFESSIONS[p]["workplace"] if p else None
