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
- To persist bookings/slots across deploys, set a persistent `DATA_DIR`.

### Railway persistence (important)

If you redeploy and data disappears, your app is writing to ephemeral container storage.

1. Add a Railway Volume to your service.
2. Set env var `DATA_DIR` to a path inside that volume, for example:
   - `/data/lokalabiltvattarna-data`
3. Redeploy.

The app stores these files in `DATA_DIR`:
- `slots.json`
- `bookings.json`
- `bookings.csv`

On startup, the app will also do a one-time migration from local `./data` into `DATA_DIR` if the destination files do not exist yet.

## Notes

- Frontend file is served from project root: `index.html`
- Booking/slot data is stored in `DATA_DIR` (defaults to `./data` if no persistent path is configured)
- Change `ADMIN_PASSWORD` in `app.py` before production use
