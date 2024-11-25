from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import socket
import struct
import time
import csv
import keyboard
from data_type import data_types

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

HOST = '0.0.0.0'
PORT = 5000
PACKET_SIZE = 212
ids = [0, 2, 3]
config = [[3, 3], [1, 1]]
received_data = []
chunk_size = 4

def int_to_bytes(value):
    return value.to_bytes(2, byteorder='big')

# Function to unpack as signed int (4 bytes)
def unpack_int(data):
    return struct.unpack('<i', data)[0]

# Function to unpack as unsigned int (4 bytes)
def unpack_uint(data):
    return struct.unpack('<I', data)[0]

# Function to unpack as float (4 bytes)
def unpack_float(data):
    return struct.unpack('<f', data)[0]

@app.route('/update', methods=['POST'])
def update_config():
    global config
    data = request.json
    variable_id = data.get('id')
    new_value = data.get('value')

    if variable_id is not None and new_value is not None:
        for entry in config:
            if entry[0] == variable_id:
                entry[1] = new_value
                break
    return jsonify({"message": "Config updated", "config": config})

@app.route('/data', methods=['GET'])
def get_received_data():
    return jsonify(received_data)

def start_server():
    with open("received_data.csv", mode="a", newline="") as csv_file:
        csv_writer = csv.writer(csv_file)

        # Write the header row dynamically based on the data_types
        header = [name for name, _ in data_types]  # Extract variable names
        csv_writer.writerow(header)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.bind((HOST, PORT))
            server_socket.listen()
            print(f"Server listening on {HOST}:{PORT}")

            while True:
                print("Waiting for a new client connection...")
                conn, addr = server_socket.accept()
                with conn:
                    print(f"Connected by {addr}")
                    conn.settimeout(1.0)

                    packet = b's' + bytes(ids) + b'\n'
                    conn.sendall(packet)
                    print(f"Config variables are: {ids}")
                    index = 0
                    while True:
                        start_time = time.time()
                        try:
                            # Receive data
                            data = conn.recv(PACKET_SIZE)
                            if not data:
                                print(f"Client {addr} disconnected")
                                break
                            chunks = [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]

                            if len(data) == PACKET_SIZE:  # Check if packet is 212 bytes long
                                row = []

                                # Process each chunk
                                for i, chunk in enumerate(chunks):
                                    if i < len(data_types):  # Ensure the index doesn't go out of range
                                        name, data_type = data_types[i]  # Get the name and data type
                                        values = {"name": name}

                                        # Perform unpacking based on the data type
                                        if data_type == "int":
                                            values["value"] = unpack_int(chunk)
                                        elif data_type == "uint":
                                            values["value"] = unpack_uint(chunk)
                                        elif data_type == "float":
                                            values["value"] = unpack_float(chunk)

                                        # Add the unpacked value to the row in the order of header
                                        row.append(values["value"])
                                        # print(f"{name}")
                                        

                                # Write the processed row to the CSV
                                csv_writer.writerow(row)

                                # Store the processed data into the received_data list
                                received_data.append({name: row[i] for i, (name, _) in enumerate(data_types)})
                                # print(received_data)

                                # Emit the data to all connected clients in real-time
                                socketio.emit('live_data', {'data': {name: row[i] for i, (name, _) in enumerate(data_types)}})
                                index += 1
                                print(index)
                        except socket.timeout:
                            print("No data received within timeout period. Reconnecting...")
                            break

                        except socket.error as e:
                            print(f"Socket error: {e}")
                            break

                        elapsed_time = time.time() - start_time
                        time_to_wait = max(0, 0.05 - elapsed_time)
                        time.sleep(time_to_wait)

if __name__ == "__main__":
    from threading import Thread
    Thread(target=lambda: socketio.run(app, host="0.0.0.0", port=5001)).start()
    start_server()
