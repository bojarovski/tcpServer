import serial
import time
from threading import Thread
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import struct
from data_type import data_types

# Flask app and Socket.IO setup
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

# Server configuration
HOST = '0.0.0.0'
PORT = 5000
SOCKET_PORT = 5001
PACKET_SIZE = 250  # Packet size from serial
received_data = []
chunk_size = 4

# Serial port configuration
serial_port = 'COM3'  # Replace with your serial port
baud_rate = 115200
serial_connection = None

# Helper functions for unpacking data
def unpack_int(data):
    return struct.unpack('<i', data)[0]

def unpack_uint(data):
    return struct.unpack('<I', data)[0]

def unpack_float(data):
    return struct.unpack('<f', data)[0]

# Flask route to retrieve received data
@app.route('/data', methods=['GET'])
def get_received_data():
    return jsonify(received_data)

# Connect to the serial device
def connect_to_serial():
    global serial_connection
    while serial_connection is None:
        try:
            serial_connection = serial.Serial(serial_port, baud_rate, timeout=1)
        except serial.SerialException as e:
            print(f"Failed to connect to the serial port: {e}")
            time.sleep(5)

# Read data from the serial port
def read_from_serial():
    global received_data, serial_connection
    connect_to_serial()
    index = 0
    while True:
        try:
            data = serial_connection.read(PACKET_SIZE)

            # Extract the first byte and convert it to a character
            packet_type_char = chr(data[0])  # Convert first byte directly to a character
            print(f"Packet Type (char): {packet_type_char}")

            # Extract the second byte and convert it to an integer
            packet_part_int = data[1]  # The second byte is already an integer
            print(f"Packet Part (int): {packet_part_int}")
            
            if len(data) == PACKET_SIZE:
                chunks = [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]
                row = []


                for i, chunk in enumerate(chunks):
                    if i < len(data_types):
                        name, data_type = data_types[i]
                        values = {"name": name}

                        if data_type == "int":
                            values["value"] = unpack_int(chunk)
                        elif data_type == "uint":
                            values["value"] = unpack_uint(chunk)
                        elif data_type == "float":
                            values["value"] = unpack_float(chunk)

                        row.append(values["value"])

                # Store received data and emit via WebSocket
                received_data.append({name: row[i] for i, (name, _) in enumerate(data_types)})
                # index= index +1
                # print (index)
                socketio.emit('live_data', {'data': {name: row[i] for i, (name, _) in enumerate(data_types)}})

        except serial.SerialException as e:
            print(f"Serial connection error: {e}")
            serial_connection = None
            connect_to_serial()
        except Exception as e:
            print(f"Error reading from serial: {e}")
            time.sleep(1)

# Start reading serial data in a separate thread
def start_serial_reading():
    serial_thread = Thread(target=read_from_serial, daemon=True)
    serial_thread.start()

# Flask route to update configuration
@app.route('/update', methods=['POST'])
def update_config():
    config = request.json
    print(f"Received config update: {config}")
    # Implement config updates
    return jsonify({"message": "Config updated successfully"}), 200

if __name__ == "__main__":
    # Start Socket.IO in a separate thread
    Thread(target=lambda: socketio.run(app, host="0.0.0.0", port=SOCKET_PORT), daemon=True).start()

    # Start reading serial data
    start_serial_reading()

    # Run Flask server
    app.run(host=HOST, port=PORT)
