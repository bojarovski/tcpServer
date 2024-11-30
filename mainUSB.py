import serial
import time
from threading import Thread
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import struct
from data_type import data_types

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

HOST = '0.0.0.0'
PORT = 5000
PACKET_SIZE = 210
received_data = []
chunk_size = 4

# Global serial object (replace '/dev/ttyUSB0' with your port)
serial_port = 'COM3'  # Example: '/dev/ttyUSB0' on Linux, 'COM3' on Windows
baud_rate = 115200  # Match with the baud rate used in the ESP32 code
serial_connection = None  # Initially set to None

# Flask Route for data
@app.route('/data', methods=['GET'])
def get_received_data():
    return jsonify(received_data)

def unpack_int(data):
    return struct.unpack('<i', data)[0]

def unpack_uint(data):
    return struct.unpack('<I', data)[0]

def unpack_float(data):
    return struct.unpack('<f', data)[0]

def connect_to_serial():
    """
    Attempts to establish a connection to the serial device.
    """
    global serial_connection
    while serial_connection is None:
        try:
            print("Attempting to connect to the serial device...")
            serial_connection = serial.Serial(serial_port, baud_rate, timeout=1)
            print(f"Connected to serial port: {serial_port}")
        except serial.SerialException as e:
            print(f"Failed to connect to the serial port: {e}")
            time.sleep(5)  # Wait for 5 seconds before trying again

def read_from_serial():
    """
    Reads data from the serial port and processes it.
    """
    global received_data, serial_connection

    # Ensure the serial connection is established
    connect_to_serial()

    while True:
        try:
            # Read a packet of size 210
            data = serial_connection.read(PACKET_SIZE)

            # Print the raw packet before unpacking
            print(f"Received raw packet: {data}")

            # Check the length of the data received
            print(f"Length of received data: {len(data)}")

            # Skip empty data packets
            if len(data) == 0:
                print("No data received, skipping...")
                continue

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

                # Store received data and emit it via SocketIO
                received_data.append({name: row[i] for i, (name, _) in enumerate(data_types)})
                socketio.emit('live_data', {'data': {name: row[i] for i, (name, _) in enumerate(data_types)}})

        except serial.SerialException as e:
            print(f"Serial connection error: {e}")
            serial_connection = None  # Set connection to None if it fails
            connect_to_serial()  # Attempt to reconnect
        except Exception as e:
            print(f"Error reading from serial: {e}")
            time.sleep(1)  # Sleep before retrying if there was an error

# Start the serial reading in a separate thread
def start_serial_reading():
    serial_thread = Thread(target=read_from_serial, daemon=True)
    serial_thread.start()

@app.route('/update', methods=['POST'])
def update_config():
    # This function remains the same as before for updating the config via Flask
    pass

if __name__ == "__main__":
    # Start Flask and SocketIO server
    Thread(target=lambda: socketio.run(app, host="0.0.0.0", port=5001), daemon=True).start()

    # Start reading from the serial port
    start_serial_reading()

    # Now your server is also running and processing serial data
    app.run(host=HOST, port=PORT)
