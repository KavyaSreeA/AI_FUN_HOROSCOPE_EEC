from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import swisseph as swe
from geopy.exc import GeopyError
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]
PLANETS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY, "Venus": swe.VENUS,
    "Mars": swe.MARS, "Jupiter": swe.JUPITER, "Saturn": swe.SATURN,
    "Uranus": swe.URANUS, "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO,
}
ASPECTS = {"conjunction": 0, "sextile": 60, "square": 90, "trine": 120, "opposition": 180}
ORB = 6

_geolocator = Nominatim(user_agent="ai-fun-horoscope")
_tf = TimezoneFinder()


class AstroError(Exception):
    pass


def geocode(place):
    try:
        loc = _geolocator.geocode(place, timeout=10)
    except GeopyError as exc:
        raise AstroError(f"Could not look up place right now: {exc}") from exc
    if not loc:
        raise AstroError(f"Could not find a place called '{place}'. Try 'City, Country'.")
    tz = _tf.timezone_at(lat=loc.latitude, lng=loc.longitude)
    if not tz:
        raise AstroError("Could not determine the timezone for that place.")
    return loc.latitude, loc.longitude, tz, loc.address


def _pos(lon):
    lon %= 360
    sign = int(lon // 30)
    deg = lon - sign * 30
    return {"sign": SIGNS[sign], "degree": round(deg, 2), "longitude": round(lon, 4)}


def _julian_day(dt_utc):
    hour = dt_utc.hour + dt_utc.minute / 60 + dt_utc.second / 3600
    return swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, hour)


def _planet_positions(jd):
    out = {}
    for name, pid in PLANETS.items():
        vals, _ = swe.calc_ut(jd, pid)
        p = _pos(vals[0])
        p["retrograde"] = vals[3] < 0
        out[name] = p
    return out


def _house_of(lon, cusps):
    for i in range(12):
        start, end = cusps[i], cusps[(i + 1) % 12]
        if start <= end:
            if start <= lon < end:
                return i + 1
        elif lon >= start or lon < end:
            return i + 1
    return 1


def _aspects(a, b, same_chart):
    found = []
    names_a, names_b = list(a), list(b)
    for i, na in enumerate(names_a):
        for j, nb in enumerate(names_b):
            if same_chart and j <= i:
                continue
            diff = abs(a[na]["longitude"] - b[nb]["longitude"]) % 360
            diff = min(diff, 360 - diff)
            for aname, angle in ASPECTS.items():
                orb = abs(diff - angle)
                if orb <= ORB:
                    found.append({"a": na, "b": nb, "aspect": aname, "orb": round(orb, 2)})
    return sorted(found, key=lambda x: x["orb"])


def birth_chart(date_str, time_str, place):
    lat, lon, tzname, address = geocode(place)
    try:
        local = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError as exc:
        raise AstroError("Date must be YYYY-MM-DD and time HH:MM (24h).") from exc
    local = local.replace(tzinfo=ZoneInfo(tzname))
    jd = _julian_day(local.astimezone(timezone.utc))

    planets = _planet_positions(jd)
    cusps, ascmc = swe.houses(jd, lat, lon, b"P")
    for p in planets.values():
        p["house"] = _house_of(p["longitude"], cusps)

    return {
        "place": address,
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "timezone": tzname,
        "utc_offset": local.strftime("%z"),
        "ascendant": _pos(ascmc[0]),
        "midheaven": _pos(ascmc[1]),
        "planets": planets,
        "houses": [{"house": i + 1, **_pos(c)} for i, c in enumerate(cusps)],
        "aspects": _aspects(planets, planets, True),
    }


def transits(natal):
    now = datetime.now(timezone.utc)
    current = _planet_positions(_julian_day(now))
    asp = [
        t for t in _aspects(current, natal["planets"], False)
        if t["a"] not in ("Moon",) or t["orb"] <= 3
    ]
    return {
        "as_of": now.strftime("%Y-%m-%d %H:%M UTC"),
        "planets": current,
        "aspects_to_natal": [
            {"transiting": t["a"], "natal": t["b"], "aspect": t["aspect"], "orb": t["orb"]}
            for t in asp
        ][:15],
    }
