from flask import Flask, request, jsonify
from flask_sockets import Sockets
import sqlite3
import datetime
import pytz
import json
from calculations import haversine, calcular_metricas_diarias

app = Flask(__name__)
sockets = Sockets(app)
DATABASE = 'gps_data.db'
CONNECTED_CLIENTS = set()

def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS gps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tracker_id TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            timestamp TEXT NOT NULL,
            date TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@sockets.route('/ws')
def echo_socket(ws):
    print("Tentativa de conexão WebSocket recebida!")
    CONNECTED_CLIENTS.add(ws)
    try:
        print("Conexão WebSocket estabelecida (dentro do try)!")
        while not ws.closed:
            message = ws.receive()
            if message:
                print(f"Mensagem recebida: {message}")
                # Você pode adicionar lógica para receber mensagens do cliente aqui, se necessário
                pass
    except Exception as e:
        print(f"Erro no WebSocket: {e}")
    finally:
        CONNECTED_CLIENTS.remove(ws)
        print("Conexão WebSocket fechada (finally)!")

def send_latest_location():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT tracker_id, latitude, longitude, timestamp FROM gps ORDER BY id DESC LIMIT 1")
    latest_location = cursor.fetchone()
    conn.close()
    if latest_location:
        location_data = dict(latest_location)
        for client in list(CONNECTED_CLIENTS):
            try:
                client.send(json.dumps(location_data))
            except Exception as e:
                print(f"Erro ao enviar mensagem para o cliente: {e}")

@app.route('/receber_localizacao', methods=['POST'])
def receber_localizacao():
    data = request.get_json()
    if not data or 'latitude' not in data or 'longitude' not in data or 'timestamp' not in data or 'tracker_id' not in data:
        return jsonify({'status': 'erro', 'mensagem': 'Dados incompletos (tracker_id ausente)'}), 400

    tracker_id = data['tracker_id']

    try:
        ts = datetime.datetime.fromtimestamp(data['timestamp'] / 1000.0)
        ts_str = ts.isoformat()
        date_str = ts.strftime('%Y-%m-%d') # Extrai a data
    except Exception as e:
        return jsonify({'status': 'erro', 'mensagem': str(e)}), 500

    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('INSERT INTO gps (tracker_id, latitude, longitude, timestamp, date) VALUES (?, ?, ?, ?, ?)',
                    (tracker_id, data['latitude'], data['longitude'], ts_str, date_str))
        conn.commit()
        conn.close()

        send_latest_location() # Chama a função para enviar a última localização
    except Exception as e:
        return jsonify({'status': 'erro', 'mensagem': str(e)}), 500

    print(f"Recebido do Tracker {tracker_id}: Latitude {data['latitude']}, Longitude {data['longitude']} em {ts_str} ({date_str})")
    return jsonify({'status': 'sucesso'}), 200

@app.route('/relatorio_diario/<date>/<tracker_id>', methods=['GET'])
def relatorio_diario(date, tracker_id):
    report_data = calcular_metricas_diarias(date, tracker_id, DATABASE)

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT timestamp FROM gps WHERE date = ? AND tracker_id = ? ORDER BY timestamp ASC', (date, tracker_id))
    timestamps_data = c.fetchall()
    conn.close()

    first_timestamp_brt_str = ""
    last_timestamp_brt_str = ""

    if timestamps_data and len(timestamps_data) > 0:
        brasilia_tz = pytz.timezone('America/Sao_Paulo')

        first_timestamp_utc = datetime.datetime.fromisoformat(timestamps_data[0][0])
        last_timestamp_utc = datetime.datetime.fromisoformat(timestamps_data[-1][0])

        first_timestamp_utc = pytz.utc.localize(first_timestamp_utc)
        last_timestamp_utc = pytz.utc.localize(last_timestamp_utc)

        first_timestamp_brt = first_timestamp_utc.astimezone(brasilia_tz)
        last_timestamp_brt = last_timestamp_utc.astimezone(brasilia_tz)

        first_timestamp_brt_str = first_timestamp_brt.strftime('%Y-%m-%d %H:%M:%S')
        last_timestamp_brt_str = last_timestamp_brt.strftime('%Y-%m-%d %H:%M:%S')

    report = {
        'date': date,
        'tracker_id': tracker_id,
        'total_distance_km': report_data['total_distance_km'],
        'average_speed_kmh': report_data['average_speed_kmh'],
        'route_points': report_data['route_points'],
        'first_timestamp_brt': first_timestamp_brt_str,
        'last_timestamp_brt': last_timestamp_brt_str
    }

    return jsonify(report)

if __name__ == '__main__':
    app.run(debug=True)