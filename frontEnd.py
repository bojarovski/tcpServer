from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import socket
import struct
import time
import csv
import keyboard
from hashmap import Variables

app = Flask(__name__)
CORS(app)
# socketio = SocketIO(app)
socketio = SocketIO(app, cors_allowed_origins="*")
HOST = '0.0.0.0'
PORT = 5000
PACKET_SIZE = 10
ids = [0, 2, 3]
config = [[3, 3], [1, 1]]
received_data = []

def int_to_bytes(value):
    return value.to_bytes(2, byteorder='big')

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
        csv_writer.writerow([var.name for var in Variables])

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

                    while True:
                        start_time = time.time()
                        try:
                            data = conn.recv(PACKET_SIZE)
                            if not data:
                                print(f"Client {addr} disconnected")
                                break

                            values = struct.unpack('<5h', data)
                            print("Received data:", values)
                            csv_writer.writerow(values)

                            received_data.append(values)

                            # Emit data to all connected clients in real-time
                            socketio.emit('live_data', {'data': values})

                            if keyboard.is_pressed("k"):
                                packet = b'c'
                                for id_val in config:
                                    id_byte = bytes([id_val[0]])
                                    value_bytes = int_to_bytes(id_val[1])
                                    packet += id_byte + value_bytes
                                packet += b'\n'
                                conn.sendall(packet)

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
