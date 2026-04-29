from flask import Flask, jsonify, request, send_from_directory
import json
import csv
import os
from datetime import datetime

BASE_DIR = os.path.dirname(__file__)
app = Flask(__name__)

DATA_DIR = os.environ.get("APP_DATA_DIR", os.path.join(BASE_DIR, "data"))
DATA_FILE = os.environ.get("APP_DATA_FILE", os.path.join(DATA_DIR, "app-data.json"))
CSV_FILE = os.environ.get("APP_CSV_FILE", os.path.join(DATA_DIR, "bookings.csv"))
LEGACY_SLOTS_FILE = os.path.join(DATA_DIR, "slots.json")
LEGACY_BOOKINGS_FILE = os.path.join(DATA_DIR, "bookings.json")
ADMIN_PASSWORD = "admin123"  # Change in production

os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
os.makedirs(os.path.dirname(CSV_FILE), exist_ok=True)

# ── helpers ─────────────────────────────────────────────────────────────────

def read_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            data = json.load(f)
        if isinstance(data, dict):
            data.setdefault("slots", {})
            data.setdefault("bookings", [])
            return data

    # one-time migration fallback from old files
    slots = {}
    bookings = []
    if os.path.exists(LEGACY_SLOTS_FILE):
        with open(LEGACY_SLOTS_FILE) as f:
            slots = json.load(f)
    if os.path.exists(LEGACY_BOOKINGS_FILE):
        with open(LEGACY_BOOKINGS_FILE) as f:
            bookings = json.load(f)
    data = {"slots": slots, "bookings": bookings}
    write_data(data)
    return data

def write_data(data):
    tmp_file = f"{DATA_FILE}.tmp"
    with open(tmp_file, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_file, DATA_FILE)

def export_csv(bookings):
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
    slots = read_data()["slots"]
    return jsonify(slots)

@app.route('/api/slots', methods=['POST'])
def set_slots():
    data = request.json
    if data.get('admin_password') != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 403
    slots = data.get('slots', {})
    current = read_data()
    current["slots"] = slots
    write_data(current)
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
    bookings = read_data()["bookings"]
    return jsonify(bookings)

@app.route('/api/bookings', methods=['POST'])
def create_booking():
    data = request.json
    required = ['name', 'phone', 'address', 'service', 'date', 'time']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'Missing field: {field}'}), 400

    data_store = read_data()
    bookings = data_store["bookings"]
    slots = data_store["slots"]

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
    data_store["bookings"] = bookings
    write_data(data_store)
    export_csv(bookings)

    return jsonify({'success': True, 'booking_id': booking['id']})

@app.route('/api/bookings/<booking_id>', methods=['DELETE'])
def delete_booking(booking_id):
    data = request.json or {}
    if data.get('admin_password') != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 403
    data_store = read_data()
    bookings = data_store["bookings"]
    bookings = [b for b in bookings if b['id'] != booking_id]
    data_store["bookings"] = bookings
    write_data(data_store)
    export_csv(bookings)
    return jsonify({'success': True})

@app.route('/api/availability', methods=['GET'])
def get_availability():
    """Public endpoint: returns slots with how many spots remain."""
    date = request.args.get('date')
    if not date:
        return jsonify({'error': 'date param required'}), 400

    data_store = read_data()
    slots = data_store["slots"]
    bookings = data_store["bookings"]

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
    bookings = read_data()["bookings"]
    export_csv(bookings)
    return send_from_directory(os.path.dirname(CSV_FILE), os.path.basename(CSV_FILE), as_attachment=True)

if __name__ == '__main__':
    read_data()
    port = int(os.environ.get("PORT", "5000"))
    app.run(host='0.0.0.0', port=port, debug=False)
