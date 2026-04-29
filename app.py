from flask import Flask, jsonify, request, send_from_directory
import json
import csv
import os
from datetime import datetime

BASE_DIR = os.path.dirname(__file__)
app = Flask(__name__)

def resolve_data_dir():
    """
    Pick a persistent data directory when available.
    Priority:
    1) DATA_DIR env var
    2) RAILWAY_VOLUME_MOUNT_PATH env var (Railway volume)
    3) /data if present
    4) local ./data fallback
    """
    explicit = os.environ.get("DATA_DIR")
    if explicit:
        return explicit

    railway_volume = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")
    if railway_volume:
        return os.path.join(railway_volume, "lokalabiltvattarna-data")

    if os.path.isdir("/data"):
        return "/data/lokalabiltvattarna-data"

    return os.path.join(BASE_DIR, "data")


def maybe_migrate_local_data(target_dir):
    """
    One-time best-effort migration from local ./data into persistent target dir.
    """
    local_dir = os.path.join(BASE_DIR, "data")
    if os.path.abspath(local_dir) == os.path.abspath(target_dir):
        return
    if not os.path.isdir(local_dir):
        return

    for filename in ["slots.json", "bookings.json", "bookings.csv"]:
        src = os.path.join(local_dir, filename)
        dst = os.path.join(target_dir, filename)
        if os.path.exists(src) and not os.path.exists(dst):
            with open(src, "rb") as in_f, open(dst, "wb") as out_f:
                out_f.write(in_f.read())


DATA_DIR = resolve_data_dir()
SLOTS_FILE = os.path.join(DATA_DIR, 'slots.json')
BOOKINGS_FILE = os.path.join(DATA_DIR, 'bookings.json')
CSV_FILE = os.path.join(DATA_DIR, 'bookings.csv')
ADMIN_PASSWORD = "admin123"  # Change in production

os.makedirs(DATA_DIR, exist_ok=True)
maybe_migrate_local_data(DATA_DIR)

# ── helpers ─────────────────────────────────────────────────────────────────

def load_json(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def export_csv():
    bookings = load_json(BOOKINGS_FILE, [])
    if not bookings:
        return
    keys = ["id", "name", "phone", "address", "district", "service", "date", "time", "notes", "created_at"]
    with open(CSV_FILE, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(bookings)

# ── static / index ────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')

# ── slots API ─────────────────────────────────────────────────────────────

@app.route('/api/slots', methods=['GET'])
def get_slots():
    slots = load_json(SLOTS_FILE, {})
    return jsonify(slots)

@app.route('/api/slots', methods=['POST'])
def set_slots():
    data = request.json
    if data.get('admin_password') != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 403
    slots = data.get('slots', {})
    save_json(SLOTS_FILE, slots)
    return jsonify({'success': True})

# ── bookings API ──────────────────────────────────────────────────────────

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.json or {}
    if data.get('admin_password') != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 403
    return jsonify({'success': True})

@app.route('/api/bookings', methods=['GET'])
def get_bookings():
    pw = request.args.get('admin_password', '')
    if pw != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 403
    bookings = load_json(BOOKINGS_FILE, [])
    return jsonify(bookings)

@app.route('/api/bookings', methods=['POST'])
def create_booking():
    data = request.json
    required = ['name', 'phone', 'address', 'service', 'date', 'time']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'Missing field: {field}'}), 400

    bookings = load_json(BOOKINGS_FILE, [])
    slots = load_json(SLOTS_FILE, {})

    # Check slot availability
    date = data['date']
    time = data['time']
    taken = [b for b in bookings if b['date'] == date and b['time'] == time]
    date_slots = slots.get(date, [])
    slot_info = next((s for s in date_slots if s['time'] == time), None)

    if not slot_info:
        return jsonify({'error': 'This time slot is not available'}), 400

    capacity = slot_info.get('capacity', 1)
    if len(taken) >= capacity:
        return jsonify({'error': 'This time slot is fully booked'}), 400

    booking = {
        'id': f"BK{datetime.now().strftime('%Y%m%d%H%M%S')}",
        'name': data['name'],
        'phone': data['phone'],
        'address': data['address'],
        'district': slot_info.get('district', ''),
        'service': data['service'],
        'date': date,
        'time': time,
        'notes': data.get('notes', ''),
        'created_at': datetime.now().isoformat()
    }

    bookings.append(booking)
    save_json(BOOKINGS_FILE, bookings)
    export_csv()

    return jsonify({'success': True, 'booking_id': booking['id']})

@app.route('/api/bookings/<booking_id>', methods=['DELETE'])
def delete_booking(booking_id):
    data = request.json or {}
    if data.get('admin_password') != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 403
    bookings = load_json(BOOKINGS_FILE, [])
    bookings = [b for b in bookings if b['id'] != booking_id]
    save_json(BOOKINGS_FILE, bookings)
    export_csv()
    return jsonify({'success': True})

@app.route('/api/availability', methods=['GET'])
def get_availability():
    """Public endpoint: returns slots with how many spots remain."""
    date = request.args.get('date')
    if not date:
        return jsonify({'error': 'date param required'}), 400

    slots = load_json(SLOTS_FILE, {})
    bookings = load_json(BOOKINGS_FILE, [])

    date_slots = slots.get(date, [])
    result = []
    for slot in date_slots:
        taken = len([b for b in bookings if b['date'] == date and b['time'] == slot['time']])
        cap = slot.get('capacity', 1)
        result.append({
            'time': slot['time'],
            'capacity': cap,
            'district': slot.get('district', ''),
            'booked': taken,
            'available': cap - taken
        })

    return jsonify(result)

@app.route('/api/csv', methods=['GET'])
def download_csv():
    pw = request.args.get('admin_password', '')
    if pw != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 403
    export_csv()
    return send_from_directory(DATA_DIR, 'bookings.csv', as_attachment=True)

if __name__ == '__main__':
    os.makedirs(DATA_DIR, exist_ok=True)
    port = int(os.environ.get("PORT", "5000"))
    app.run(host='0.0.0.0', port=port, debug=False)
