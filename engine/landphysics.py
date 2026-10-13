"""🌦🧪 The life of a piece of real land, by physics and chemistry (the same rules as our planets, on Earth):

  climate  - the air is warmer the lower you are (the lapse rate: -6.5 °C per km up) and the nearer the equator;
             the seasons swing with the sun's height (latitude); the monsoon wind (from the south-west) is pushed up
             the slopes that face it, cools, and drops its rain there (orographic rain) - the hills get the most.
  soil     - rock + water + time: the sandstone (quartz grains held by iron oxide) breaks into sand; heavy monsoon
             rain washes the soluble bases (Ca, Mg, K) away, so well-drained soil turns acid and RED (the iron stays
             as hematite, Fe2O3 - laterite on old flat tops); in the wet valley bottoms the iron is reduced and river
             silt and dead leaves build a darker, richer alluvium; steep cliffs keep only bare rock.
  plants   - what can live there: sal where rain is high and the soil drains (acid red soil), teak where it is a
             little drier, bamboo along the streams (roots in water), fields on the flat silt, mango / mahua / neem
             planted round the houses, bare sandstone on the cliffs.

    life = landphysics.study(h, cell, lat, base_m, rivers_mask)   # per-cell maps + the "why" lines
"""
import math

import numpy as np

LAPSE = 6.5          # °C less per km up (the standard atmosphere)
MONSOON_FROM = 225   # degrees: the summer monsoon blows from the south-west over central India


def sea_level_mean(lat):
    """the year's mean temperature at sea level (°C): the sun's average height falls with latitude"""
    return 29.5 - 0.0045 * lat * lat


def climate(lat, elev_m, month=10):
    """-> dict: mean / this month's day and night temperature (°C), the month's rain (mm) and season"""
    t = sea_level_mean(lat) - LAPSE * elev_m / 1000.0
    swing = 2.0 + 0.32 * abs(lat)                        # the year's swing grows away from the equator
    # a monsoon land's year (not a plain sine): coldest in January, hottest in May just before the rains, the
    # monsoon clouds cool June-September, October still warm, winter from November (°C from the mean, for swing 7)
    shape = {1: -7, 2: -4.5, 3: 0, 4: 4.5, 5: 7, 6: 4, 7: 0.5, 8: 0, 9: 0, 10: -1, 11: -4.5, 12: -7}
    if lat < 0:
        month = (month + 5) % 12 + 1
    mon = t + swing / 7.0 * shape[month]
    dayn = {12: 15, 1: 15, 2: 15, 3: 16, 4: 16, 5: 14, 10: 12, 11: 14}.get(month, 7)   # clear dry air swings more
    share = {1: .01, 2: .01, 3: .01, 4: .01, 5: .02, 6: .15, 7: .32, 8: .28, 9: .15, 10: .03, 11: .005, 12: .005}
    season = ("monsoon" if 6 <= month <= 9 else "after the monsoon" if month in (10, 11) else
              "winter" if month in (12, 1, 2) else "summer")
    return {"mean_c": round(t, 1), "month_c": round(mon, 1), "day_c": round(mon + dayn / 2, 1),
            "night_c": round(mon - dayn / 2, 1), "season": season, "month_share": share[month]}


def rain_map(h, cell, base_m, annual=1100.0):
    """the year's rain (mm) per cell: more higher up and on the slopes facing the monsoon wind"""
    gy, gx = np.gradient(h, cell)                        # gy: rise per m to the north, gx: to the east
    a = math.radians(MONSOON_FROM + 180.0)               # the way the wind blows TO
    wx, wz = math.sin(a), math.cos(a)
    upslope = np.clip(gx * wx + gy * wz, 0, None)        # the ground rises along the wind: the air is pushed up
    from scipy.ndimage import uniform_filter
    upslope = uniform_filter(upslope, size=9)            # (the clouds rise over the whole hill side, not one cell)
    elev = base_m + h
    return annual * (1.0 + 0.45 * elev / 1000.0 + 1.5 * np.clip(upslope, 0, 0.35))


def study(h, cell, lat, base_m, river_mask, month=10):
    """per-cell maps: rain (mm/yr), soil kind, soil pH, colour, what grows; plus the why lines"""
    h = np.asarray(h, float)
    gy, gx = np.gradient(h, cell)
    slope = np.hypot(gx, gy)
    rain = rain_map(h, cell, base_m)
    from scipy.ndimage import distance_transform_edt as edt
    dist = edt(~river_mask) * cell
    low = h - np.percentile(h, 10)
    soil = np.full(h.shape, "red", dtype=object)
    soil[(dist < 300) & (slope < 0.04) & (low < 40)] = "alluvium"   # river silt on the low flat land
    soil[slope > 0.55] = "rock"                                      # cliffs: the soil washes off as fast as it forms
    soil[(slope < 0.02) & (h > np.percentile(h, 80))] = "laterite"  # old flat tops: leached for ages, iron left
    # acid from leaching: more rain through a draining soil = fewer bases left (pH)
    ph = 7.2 - 0.0009 * (rain - 900) * np.clip(slope * 8 + 0.3, 0.3, 1.0)
    ph[soil == "alluvium"] = 6.8
    ph[soil == "laterite"] -= 0.4
    colours = {"red": "#9a5a36", "laterite": "#8a3f26", "alluvium": "#6e5a43", "rock": "#c4a27e"}
    plant = np.full(h.shape, "teak", dtype=object)
    plant[rain > 1550] = "sal"
    plant[dist < 70] = "bamboo"
    plant[soil == "alluvium"] = "fields"
    plant[soil == "rock"] = "bare rock"
    elev = base_m + h
    c_low, c_high = climate(lat, float(elev.min()), month), climate(lat, float(elev.max()), month)
    why = [f"air: {c_low['mean_c']} °C a year on average down at {elev.min():.0f} m, {c_high['mean_c']} °C up at "
           f"{elev.max():.0f} m (−{LAPSE} °C per km up); this month ({c_low['season']}) days ~{c_low['day_c']} °C, "
           f"nights ~{c_low['night_c']} °C in the valley",
           f"rain: {rain.min():.0f}-{rain.max():.0f} mm a year - the south-west monsoon is pushed up the slopes facing "
           "it, cools and rains there (most on the high windward side)",
           "soil: sandstone sand; the heavy rain washes the bases out, so the drained soil is acid (pH "
           f"{ph[soil == 'red'].mean():.1f}) and red - its iron stays as rust-red hematite (Fe2O3); old flat tops are "
           "laterite (deep red, iron and aluminium left behind); the river flats are darker silt (alluvium, pH ~6.8)",
           "plants: sal where the rain is heaviest and the soil drains, teak where it is drier, bamboo along the "
           "streams (roots in water), fields on the silt, bare pink-buff sandstone on the cliffs"]
    return {"rain": rain, "soil": soil, "ph": ph, "colour": colours, "plant": plant, "slope": slope, "dist": dist,
            "climate": climate(lat, float(base_m + h.mean()), month), "why": why}
