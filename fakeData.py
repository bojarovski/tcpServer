from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import random
import time
from threading import Thread
import math

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Global variable to hold simulated trajectory data
received_data = []

# Maribor coordinates as the center (Latitude, Longitude)
center_latitude = 46.5547
center_longitude = 15.6459

# Radius to restrict movement (in decimal degrees for simplicity)
# Roughly 0.01 degree corresponds to ~1 km, you can adjust this for tighter control
max_latitude_change = 0.005  # Latitude change range in degrees
max_longitude_change = 0.005  # Longitude change range in degrees

# Initial values for simulation
current_latitude = center_latitude
current_longitude = center_longitude
current_speed = 300  # Initial speed in km/h
current_altitude = 10000  # Starting altitude in meters (10 km)
current_attitude = {'pitch': 0, 'roll': 0, 'yaw': 0}  # Initial attitude
flight_phase = "cruise"  # Possible values: "climb", "cruise", "descend"

@app.route('/data', methods=['GET'])
def get_received_data():
    """API endpoint to fetch received data."""
    return jsonify(received_data)

def generate_fake_data():
    """Simulates receiving fake data and emits it to connected clients."""
    global received_data, current_latitude, current_longitude, current_speed, current_attitude, current_altitude, flight_phase
    
    while True:
        # Simulate changing coordinates (latitude, longitude) within the Maribor area
        # Make sure the new coordinates are within the allowed range around Maribor
        current_latitude += random.uniform(-max_latitude_change, max_latitude_change)
        current_longitude += random.uniform(-max_longitude_change, max_longitude_change)
        
        # Simulate speed (in km/h), randomly fluctuating around current speed
        current_speed += random.uniform(-5, 5)  # Slight fluctuation in speed
        
        # Simulate pitch, roll, and yaw changes
        pitch_change = random.uniform(-2, 2)  # Smaller range for pitch
        roll_change = random.uniform(-5, 5)   # Smaller range for roll
        yaw_change = random.uniform(-10, 10)  # Smaller range for yaw
        
        # Apply the changes to the current attitude
        current_attitude['pitch'] += pitch_change
        current_attitude['roll'] += roll_change
        current_attitude['yaw'] += yaw_change

        # Simulate wind or turbulence effects on the attitude
        if random.random() < 0.1:  # 10% chance of turbulence
            current_attitude['pitch'] += random.uniform(-5, 5)  # Sharp pitch changes
            current_attitude['roll'] += random.uniform(-10, 10)  # Sharp roll changes
            current_attitude['yaw'] += random.uniform(-15, 15)   # Sharp yaw changes
        
        # Limit the attitude to avoid extreme values
        current_attitude['pitch'] = max(-90, min(90, current_attitude['pitch']))  # -90 to 90 degrees
        current_attitude['roll'] = max(-90, min(90, current_attitude['roll']))    # -90 to 90 degrees
        current_attitude['yaw'] = max(-180, min(180, current_attitude['yaw']))    # -180 to 180 degrees

        # Create a dictionary with the current values
        fake_data = {
            'coordinates': [current_latitude, current_longitude],  # Latitude and longitude as an array
            'attitude': current_attitude,
            'speed': current_speed,
            'altitude': current_altitude
        }

        # Append the generated fake data to the global list
        received_data.append(fake_data)
        
        # Emit the data to all connected clients
        socketio.emit('live_data', {'data': fake_data})
        print(f"Emitted fake data: {fake_data}")
        
        # Wait 3 seconds before sending the next data set (slower update rate)
        time.sleep(0.5)

if __name__ == "__main__":
    # Start the fake data generator in a separate thread
    Thread(target=generate_fake_data, daemon=True).start()
    
    # Start the Flask-SocketIO server
    socketio.run(app, host="0.0.0.0", port=5001)
