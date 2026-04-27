from flask import Flask, jsonify, request, send_from_directory
import json
import csv
import os
from datetime import datetime

BASE_DIR = os.path.dirname(__file__)
app = Flask(__name__)

DATA_DIR = os.path.join(BASE_DIR, 'data')
SLOTS_FILE = os.path.join(DATA_DIR, 'slots.json')
BOOKINGS_FILE = os.path.join(DATA_DIR, 'bookings.json')
CSV_FILE = os.path.join(DATA_DIR, 'bookings.csv')
ADMIN_PASSWORD = "admin123"  # Change in production

os.makedirs(DATA_DIR, exist_ok=True)

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
    keys = ["id", "name", "phone", "address", "service", "date", "time", "notes", "created_at"]
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
    slot_key = f"{date}_{time}"

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
