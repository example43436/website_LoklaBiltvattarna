# SparkWash Website

This project is now set up so a hosting provider can run it directly as a Flask app.

## Local run

1. Install dependencies:
   - `pip install -r requirements.txt`
2. Start server:
   - `python app.py`
3. Open:
   - `http://localhost:5000`

## Deploy

- The `Procfile` is included for platforms that support process files.
- Production command:
  - `gunicorn app:app`
- The app reads `PORT` automatically in `app.py`.

## Notes

- Frontend file is served from project root: `index.html`
- Booking/slot data is stored in `data/`
- Change `ADMIN_PASSWORD` in `app.py` before production use
