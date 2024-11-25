from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import socket
import struct
import time
import csv
from threading import Thread, Lock
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

server_socket = None  # Server socket
client_connections = []  # Global list to store active client connections
connections_lock = Lock()  # Lock to manage concurrent access to client_connections


def int_to_bytes(value):
    return value.to_bytes(2, byteorder='big')


def unpack_int(data):
    return struct.unpack('<i', data)[0]


def unpack_uint(data):
    return struct.unpack('<I', data)[0]


def unpack_float(data):
    return struct.unpack('<f', data)[0]


@app.route('/update', methods=['POST'])
def update_config():
    global client_connections
    try:
        data = request.json
        print("Received data for update:", data)
        
        # Extract and validate the input fields
        variable_id = int(data.get('id'))
        new_value = data.get('value')
        variable_type = data.get('type')

        print(type(variable_id), type(new_value), type(variable_type))


        if variable_id is None or new_value is None or variable_type is None:
            raise ValueError("Fields 'id', 'value', and 'type' are required.")

        # Convert variable_id to bytes (last 3 bytes only)
        variable_id_bytes = struct.pack('>I', variable_id)[-3:]  

        # Convert new_value based on variable_type
        if variable_type == "int":
            new_value_bytes = struct.pack('>i', int(new_value))
            converted_type = 'i'
        elif variable_type == "uint":
            new_value_bytes = struct.pack('>I', int(new_value))
            converted_type = 'u'
        elif variable_type == "float":
            new_value_bytes = struct.pack('>f', float(new_value))
            converted_type = 'f'
        else:
            raise ValueError(f"Unsupported type: {variable_type}. Use 'int', 'uint', or 'float'.")
        
        # Construct the packet
        packet = b'c' + variable_id_bytes + converted_type.encode('utf-8') + new_value_bytes

        # Send the packet to all connected clients
        with connections_lock:
            disconnected_clients = []
            for conn in client_connections:
                try:
                    conn.sendall(packet)
                except socket.error as e:
                    print(f"Error sending data to client: {e}")
                    disconnected_clients.append(conn)

            # Remove disconnected clients
            for conn in disconnected_clients:
                client_connections.remove(conn)
                print("Removed a disconnected client.")
        
        return jsonify({
            "message": "Config updated",
            "packet": packet.hex()  # Return packet as a hexadecimal string
        }), 200

    except ValueError as ve:
        print(f"Validation error: {ve}")
        return jsonify({"error": str(ve)}), 400

    except Exception as e:
        print(f"Error in /update: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/data', methods=['GET'])
def get_received_data():
    return jsonify(received_data)


def client_handler(conn, addr):
    """
    Handle a single client connection.
    """
    global received_data
    print(f"Client connected from {addr}")
    conn.settimeout(1.0)

    with conn:
        packet = b's'
        conn.sendall(packet)
        print(f"Request a value of variables")
        while True:
            try:
                data = conn.recv(PACKET_SIZE)
                if not data:
                    print(f"Client {addr} disconnected")
                    break
                
                chunks = [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]

                if len(data) == PACKET_SIZE:
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

                    # Write to CSV or process
                    received_data.append({name: row[i] for i, (name, _) in enumerate(data_types)})
                    socketio.emit('live_data', {'data': {name: row[i] for i, (name, _) in enumerate(data_types)}})
            except socket.timeout:
                continue
            except socket.error as e:
                print(f"Socket error with client {addr}: {e}")
                break


def start_server():
    global server_socket, client_connections
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    print(f"Server listening on {HOST}:{PORT}")

    while True:
        conn, addr = server_socket.accept()
        with connections_lock:
            client_connections.append(conn)
        Thread(target=client_handler, args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    Thread(target=lambda: socketio.run(app, host="0.0.0.0", port=5001), daemon=True).start()
    start_server()
