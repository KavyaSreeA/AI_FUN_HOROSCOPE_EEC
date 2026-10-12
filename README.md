# AI Astrologer

Enter date, time and place of birth. The app computes a real natal chart (Swiss Ephemeris: planets, Ascendant, Midheaven, Placidus houses, aspects) plus today's planetary transits, then an LLM (Groq) interprets that data into a personalised reading and forecast.

Place names are geocoded with OpenStreetMap Nominatim, so an internet connection is needed.

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # then put your GROQ_API_KEY in .env
python app.py
```

Open http://127.0.0.1:5000.

For entertainment only.
