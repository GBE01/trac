import math
import datetime
import sqlite3


def haversine(lat1, lon1, lat2, lon2):
    """
    Calcula a distância em quilômetros entre duas coordenadas usando a fórmula de Haversine.
    """
    R = 6371  # Raio da Terra em quilômetros
    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c
    return distance

def calcular_metricas_diarias(date, tracker_id, database_path):
    """
    Calcula a distância total e a velocidade média para um determinado dia e tracker.
    """
    conn = sqlite3.connect(database_path)
    c = conn.cursor()
    c.execute('SELECT latitude, longitude, timestamp FROM gps WHERE date = ? AND tracker_id = ? ORDER BY timestamp ASC', (date, tracker_id))
    data = c.fetchall()
    conn.close()

    if not data or len(data) < 2:
        return {'total_distance_km': 0, 'average_speed_kmh': 0, 'route_points': []}

    total_distance = 0
    previous_point = None
    first_timestamp = None
    last_timestamp = None
    route_points = []

    for i, point in enumerate(data):
        latitude, longitude, timestamp_str = point
        current_point = (latitude, longitude)
        timestamp = datetime.datetime.fromisoformat(timestamp_str)
        route_points.append({'latitude': latitude, 'longitude': longitude})

        if i == 0:
            first_timestamp = timestamp

        if previous_point:
            distance = haversine(previous_point[0], previous_point[1], current_point[0], current_point[1])
            total_distance += distance

        previous_point = current_point
        last_timestamp = timestamp

    average_speed = 0
    if first_timestamp and last_timestamp:
        time_difference = last_timestamp - first_timestamp
        total_seconds = time_difference.total_seconds()
        average_speed = (total_distance / total_seconds) * 3600 if total_seconds > 0 else 0 # km/h

    return {
        'total_distance_km': round(total_distance, 2),
        'average_speed_kmh': round(average_speed, 2),
        'route_points': route_points
    }