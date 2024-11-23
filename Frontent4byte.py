from flask import Flask, request, jsonify
from flask_socketio import SocketIO
from flask_cors import CORS
import socket
import struct
import time
import csv
import keyboard
from data_type import DataType

# Flask app setup
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Server configuration
HOST = '0.0.0.0'
PORT = 5000
PACKET_SIZE = 4  # Each field is 4 bytes
received_data = []

# Helper function to encode a value based on its data type
def encode_value(data_type, value):
    try:
        if data_type == "int":
            return struct.pack("<i", value)  # Little-endian signed int (4 bytes)
        elif data_type == "uint":
            # Ensure value is within the valid range for an unsigned int
            if 0 <= value <= 4294967295:
                return struct.pack("<I", value)  # Little-endian unsigned int (4 bytes)
            else:
                raise ValueError(f"Value {value} is out of range for uint.")
        elif data_type == "float":
            return struct.pack("<f", value)  # Little-endian float (4 bytes)
        else:
            raise ValueError(f"Unsupported data type: {data_type}")
    except (struct.error, ValueError) as e:
        print(f"Error encoding value {value} as {data_type}: {e}")
        return b""  # Return an empty byte sequence in case of an error

# Function to process and encode an incoming packet
def process_packet(packet):
    encoded_packet = b""
    # Iterate over 4-byte chunks in the packet
    for i in range(0, len(packet), 4):
        chunk = packet[i:i+4]
        # Ensure chunk is exactly 4 bytes long
        if len(chunk) != 4:
            print(f"Incomplete chunk received: {chunk.hex()}. Skipping...")
            continue

        # Extract DataType and encode accordingly
        try:
            data_type = list(DataType)[i // 4]
            value = struct.unpack("<i", chunk)[0]  # Assuming default signed int
            encoded_chunk = encode_value(data_type.value, value)
            encoded_packet += encoded_chunk
        except Exception as e:
            print(f"Error processing chunk {chunk.hex()}: {e}")
    
    return encoded_packet

# Flask endpoint to fetch received data
@app.route('/data', methods=['GET'])
def get_received_data():
    return jsonify(received_data)

# Server function to handle incoming connections
def start_server():
    with open("received_data.csv", mode="a", newline="") as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow([field.name for field in DataType])

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

                    while True:
                        try:
                            # Receive the expected packet size
                            packet = conn.recv(PACKET_SIZE * len(DataType))
                            if not packet:
                                print(f"Client {addr} disconnected")
                                break

                            print("Received packet:", packet)

                            # Process and encode the packet
                            encoded_packet = process_packet(packet)
                            print("Encoded packet:", encoded_packet)

                            # Save and emit the data
                            csv_writer.writerow(encoded_packet)
                            received_data.append(encoded_packet)
                            socketio.emit('live_data', {'data': encoded_packet})

                            # Send the encoded packet back to the client
                            conn.sendall(encoded_packet)

                        except socket.timeout:
                            print("Timeout. Reconnecting...")
                            break
                        except socket.error as e:
                            print(f"Socket error: {e}")
                            break

# Start the Flask app and TCP server
if __name__ == "__main__":
    from threading import Thread
    # Start the Flask SocketIO app
    Thread(target=lambda: socketio.run(app, host="0.0.0.0", port=5001)).start()
    # Start the TCP server
    start_server()
