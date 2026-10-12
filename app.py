import json
import os
from datetime import date

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

import astro

load_dotenv()

app = Flask(__name__)

TONES = ["mystical", "funny", "motivational", "romantic", "straightforward"]
FOCUSES = ["overall", "love", "career", "money", "health & energy"]
PERIODS = ["today", "this week", "this month"]
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

SYSTEM_PROMPT = (
    "You are an expert astrologer. You are given a person's real, precomputed "
    "natal chart (tropical zodiac, Placidus houses) and the current planetary transits. "
    "Base every statement ONLY on the placements and aspects provided; never invent "
    "placements. Cite the specific placements you use (e.g. 'Moon in Cancer in the 4th house', "
    "'transiting Saturn square natal Sun'). Be warm and specific, not generic. "
    "This is for entertainment: do not give medical, legal or financial advice."
)

_client = None


def get_client():
    global _client
    if _client is None and os.getenv("GROQ_API_KEY"):
        from groq import Groq

        _client = Groq()
    return _client


def compact_chart(chart):
    return {
        "ascendant": chart["ascendant"],
        "midheaven": chart["midheaven"],
        "planets": {
            n: f"{p['degree']:.1f} deg {p['sign']}, house {p['house']}"
            + (", retrograde" if p["retrograde"] else "")
            for n, p in chart["planets"].items()
        },
        "natal_aspects_between_natal_planets": chart["aspects"][:15],
    }


def generate_reading(name, chart, tr, tone, focus, period):
    prompt = (
        f"Name: {name or 'the querent'}\n"
        f"Today: {date.today():%A, %B %d, %Y}\n"
        f"Natal chart: {json.dumps(compact_chart(chart))}\n"
        f"Current transits: {json.dumps({'as_of': tr['as_of'], 'aspects_to_natal': tr['aspects_to_natal']})}\n\n"
        f"Write a {tone} astrology reading with these sections, using markdown headings:\n"
        "## Your Big Three (Sun, Moon, Rising: what each means for this person)\n"
        "## Personality & Strengths (from the natal chart)\n"
        f"## Forecast for {period} (focus: {focus}; use the current transits)\n"
        "## Advice (2-3 concrete suggestions)\n"
        "Format: plain markdown only. Headings must be exactly as written above (## ...), with no bold on headings, no horizontal rules, and short bullet lists. Do not mix natal aspects with transits. Keep it under 450 words. End with a line: "
        "'Lucky number: N | Lucky color: C | Mood: M'."
    )
    resp = get_client().chat.completions.create(
        model=MODEL,
        max_tokens=4000,
        reasoning_effort="low",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


@app.get("/")
def index():
    return render_template("index.html", tones=TONES, focuses=FOCUSES, periods=PERIODS)


@app.post("/api/reading")
def reading():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()[:40]
    dob = str(data.get("dob", "")).strip()
    tob = str(data.get("time", "")).strip()
    place = str(data.get("place", "")).strip()[:120]
    tone = data.get("tone") if data.get("tone") in TONES else TONES[0]
    focus = data.get("focus") if data.get("focus") in FOCUSES else FOCUSES[0]
    period = data.get("period") if data.get("period") in PERIODS else PERIODS[0]

    if not (dob and tob and place):
        return jsonify(error="Date of birth, time of birth and place are required."), 400
    if get_client() is None:
        return jsonify(error="GROQ_API_KEY is not set. Add it to .env and restart."), 500

    try:
        chart = astro.birth_chart(dob, tob, place)
    except astro.AstroError as exc:
        return jsonify(error=str(exc)), 400
    tr = astro.transits(chart)

    try:
        text = generate_reading(name, chart, tr, tone, focus, period)
    except Exception as exc:
        app.logger.exception("LLM call failed")
        return jsonify(error=f"LLM request failed: {exc}"), 502
    if not text:
        return jsonify(error="The model returned an empty reading. Please try again."), 502

    return jsonify(chart=chart, transits=tr, reading=text)


if __name__ == "__main__":
    app.run(debug=True, port=int(os.getenv("PORT", "5000")))
