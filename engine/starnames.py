"""⭐ Known names for the stars of the Milky Way (the game's only galaxy): the real proper names of bright stars (IAU list),
the Indian names of the nakshatras and the Saptarishi, and the famous nearby and planet-hosting stars. Past those, a star gets
a real-style catalogue number (HD / HIP / Gliese / Kepler / TOI), the way astronomers name the millions without a proper name.
🎮 game rule: the name is real, the star wearing it is the game's (its place, size and planets come from engine/galaxy.py)."""
import hashlib

PROPER = """Sirius Canopus Arcturus Vega Capella Rigel Procyon Achernar Betelgeuse Hadar Altair Acrux Aldebaran Antares Spica
Pollux Fomalhaut Deneb Mimosa Regulus Adhara Castor Shaula Gacrux Bellatrix Elnath Miaplacidus Alnilam Alnair Alnitak Alioth
Dubhe Mirfak Wezen Sargas Avior Alkaid Menkalinan Atria Alhena Peacock Mirzam Alphard Polaris Hamal Algieba Diphda Nunki
Menkent Mirach Alpheratz Rasalhague Kochab Saiph Denebola Algol Tiaki Suhail Alphecca Mintaka Sadr Eltanin Schedar Naos Almach
Caph Izar Dschubba Merak Ankaa Girtab Enif Scheat Sabik Phecda Aludra Markeb Markab Aljanah Acrab Zosma Arneb Gienah Ruchbah
Unukalhai Kraz Zubeneschamali Zubenelgenubi Sheratan Phact Tarazed Alderamin Algenib Albireo Mizar Alcor Thuban Vindemiatrix
Alcyone Electra Maia Merope Taygeta Atlas Pleione Celaeno Asterope Mira Rasalgethi Sadalsuud Sadalmelik Nashira Alshain Sulafat
Sheliak Kornephoros Chara Zaniah Porrima Heze Syrma Seginus Nekkar Muphrid Menkar Mesarthim Botein Alrescha Skat Ancha Biham
Homam Matar Sadalbari Errai Alfirk Kurhah Alkalurops Alsafi Fafnir Edasich Giausar Rastaban Grumium Altais Aldhibah Atik Menkib
Hassaleh Haedus Saclateni Mahasim Tejat Mebsuta Alzirr Mekbuda Propus Wasat Alkes Talitha Muscida Chertan Subra Rasalas
Adhafera Algorab Minkar Alchiba Toliman Alsephina Larawag Fang Alniyat Paikauhale Xamidimura Pipirima Lesath Jabbah Alnasl
Kaus Ascella Albaldah Rukbat Arkab Terebellum Okul Salm Sadachbia Ancha Situla Bunda Baham Sham Anser Peacock Alathfar
Azelfafage Azmidi Aspidiske Aldulfin Rotanev Sualocin Pherkad Yildun Alruba Tyl Alya Sabik Marfik Cebalrai Kajam Alhena
Mebsuta Wasat Tureis Naos Regor Avior Markeb Suhail Gomeisa Muliphein Furud Wezen Unurgunite Aludra Lucilinburhuz Alterf
Algenubi Rasalas Dubhe Megrez Tania Alula Taiyangshou Chalawan Copernicus Galileo Lich Fomalhaut Ain Prima Hyadum Secunda
Tabit Beid Keid Zaurak Rana Azha Acamar Sceptrum Theemin Zibal Cursa Kang Khambalia Syrma Elgafar Zavijava Auva Kraz Alkaphrah""".split()

INDIAN = """Ashvini Bharani Krittika Rohini Mrigashira Ardra Punarvasu Pushya Ashlesha Magha Purva-Phalguni Uttara-Phalguni Hasta
Chitra Swati Vishakha Anuradha Jyeshtha Mula Purva-Ashadha Uttara-Ashadha Shravana Dhanishta Shatabhisha Purva-Bhadrapada
Uttara-Bhadrapada Revati Abhijit Kratu Pulaha Pulastya Atri Angiras Vasishtha Marichi Arundhati Dhruva Agastya Lubdhaka
Brahmahridaya Prajapati Apamvatsa Agni Mitra Varuna Savitar Aryaman Indra Soma Surya Chandra Tara Sitara""".split()

NEAR = ["Proxima Centauri", "Rigil Kentaurus", "Barnard's Star", "Wolf 359", "Lalande 21185", "Ross 128", "Luyten's Star",
        "Tau Ceti", "Epsilon Eridani", "Gliese 581", "Gliese 667 C", "Kepler-22", "Kepler-186", "Kepler-442", "Kepler-452",
        "TRAPPIST-1", "LHS 1140", "Teegarden's Star", "Ross 154", "Struve 2398", "Groombridge 34", "Epsilon Indi",
        "Kapteyn's Star", "Van Maanen's Star", "61 Cygni", "Lacaille 9352", "YZ Ceti", "Gliese 1061", "Wolf 1061", "HD 40307",
        "55 Cancri", "51 Pegasi", "47 Ursae Majoris", "Upsilon Andromedae", "HD 209458", "WASP-12", "WASP-121", "K2-18",
        "TOI-700", "Gliese 436", "Gliese 1214", "GJ 357", "HR 8799", "Beta Pictoris", "Kepler-16", "Kepler-62", "Kepler-69",
        "Kepler-90", "Kepler-1649", "LTT 1445", "AU Microscopii", "Fomalhaut b", "PSR B1257+12", "Gliese 876", "HD 189733"]
NEAR = [n for n in NEAR if n != "Fomalhaut b"]


# the stars of the journey's own worlds (engine/saga.py world(n)): fitting names, kept out of the shared pool
SPECIAL = {420: "Dhruva", 502: "Agni", 533: "Rigel", 312: "Alnasl", 424: "Varuna", 422: "Rohini", 513: "Swati", 153: "Altair", 160: "Deneb", 163: "Ascella"}


def _all():
    seen, out = set(SPECIAL.values()), []
    for n in INDIAN + PROPER + NEAR:                              # (Indian names first: our players' own sky)
        n = n.replace("-", " ") if n in INDIAN else n
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


ALL = _all()
_ORDER = {}


def _h(*a):
    return int(hashlib.sha256("|".join(map(str, a)).encode()).hexdigest()[:12], 16)


def name(index):
    """the known name of Milky Way star `index`: a proper name (shuffled the same way for every player), then catalogue numbers"""
    if index in SPECIAL:
        return SPECIAL[index]
    if not _ORDER:
        _ORDER["o"] = sorted(range(len(ALL)), key=lambda i: _h("mw-names", i))
    o = _ORDER["o"]
    if 0 <= index < len(o):
        return ALL[o[index]]
    h = _h("mw-cat", index)
    n = index * 97 + h % 97                                       # (never the same number twice)
    kind = h % 5
    if kind == 0:
        return f"HD {10000 + n}"
    if kind == 1:
        return f"HIP {1000 + n}"
    if kind == 2:
        return f"Gliese {100 + n // 40}{'ABCDEFGHJK'[n % 10]}"
    if kind == 3:
        return f"Kepler-{10 + n // 20}"
    return f"TOI-{100 + n // 9}"
