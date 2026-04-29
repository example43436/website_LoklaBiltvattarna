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
- Persistent data location can be configured with environment variables:
  - `APP_DATA_FILE` (default: `data/app-data.json`)
  - `APP_CSV_FILE` (default: `data/bookings.csv`)
  - `APP_DATA_DIR` (optional base dir used by defaults)

### Railway persistence

To keep bookings and slots after redeploys, store `APP_DATA_FILE` on a mounted persistent volume path in Railway (for example `/data/app-data.json`).
If `APP_DATA_FILE` points to ephemeral container storage, data will reset on deploy.

## Notes

- Frontend file is served from project root: `index.html`
- Booking/slot data is stored in `data/`
- Change `ADMIN_PASSWORD` in `app.py` before production use
