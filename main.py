import serial
import threading
import time
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import struct
from reciveDataEnum import data_types
from reciveConfigEnum import recived_config_data
# Flask app and Socket.IO setup
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", logger=False, engineio_logger=False) #SET logger=True, engineio_logger=True to see logs

# Server configuration
HOST = '0.0.0.0'
PORT = 5000
SOCKET_PORT = 5001
PACKET_SIZE = 250  # Packet size from serial
START_BYTE = 0xAA
END_BYTE = 0xFE
chunk_size = 4
received_data = []
received_config = []
serial_port = 'COM3'
baud_rate = 115200
serial_connection = None
ser = serial.Serial(serial_port, baud_rate, timeout=0.01)
# Data types for decoding

# Helper functions for unpacking data
def unpack_int(data):
    return struct.unpack('<i', data)[0]

def unpack_uint(data):
    return struct.unpack('<I', data)[0]

def unpack_float(data):
    return struct.unpack('<f', data)[0]

def calculate_checksum(data):
    checksum = 0
    for byte in data:
        checksum ^= byte  # XOR each byte with the current checksum
    return checksum

# Create a packet for sending
def create_packet(data):
    if len(data) != 250:
        raise ValueError("Data must be exactly 250 bytes long")

    packet = bytearray([START_BYTE, START_BYTE, START_BYTE, START_BYTE])
    packet.extend(data)
    packet.append(calculate_checksum(data))
    packet.extend([END_BYTE, END_BYTE, END_BYTE, END_BYTE])
    return packet

def send_packet(data):
    packet = create_packet(data)
    ser.write(packet)
    print(f"Sent packet: {packet}")

# Process data from the buffer
# Process data from the buffer
def process_buffer(buffer):
    global received_data, received_config
    while len(buffer) >= 259:  # Wait until buffer has at least 259 bytes (header + payload + checksum)
        i = 0
        while True:
            if len(buffer) - i < 259:
                time.sleep(0.01)
                return
            if buffer[i:i + 4] == bytearray([START_BYTE, START_BYTE, START_BYTE, START_BYTE]):
                break
            i += 1

        # Validate checksum
        payload = buffer[i + 4:i + 254]
        checksum = buffer[i + 254]
        if calculate_checksum(payload) != checksum:
            print("Checksum not correct!")
            del buffer[:i + 259]
            continue
        first_char = chr(payload[0])  # Convert first byte to char
        second_int = payload[1]  # Convert second byte to integer
        # print(first_char)
        # print(second_int)
        remaining_payload = payload[2:]

        # Decode data based on type
        if first_char == "T":
            decode_live_data(remaining_payload)
        elif first_char == "C":
            print("C")
        elif first_char == "S":
            decode_config_data(remaining_payload)
        del buffer[:i + 259]

def decode_live_data(payload):
    chunks = [payload[j:j + chunk_size] for j in range(0, len(payload), chunk_size)]
    row = []
    for k, chunk in enumerate(chunks):
        if k < len(data_types):
            name, data_type = data_types[k]
            value = None
            if data_type == "int":
                value = unpack_int(chunk)
            elif data_type == "uint":
                value = unpack_uint(chunk)
            elif data_type == "float":
                value = unpack_float(chunk)
            row.append(value)
    received_data.append({name: row[m] for m, (name, _) in enumerate(data_types)})
    socketio.emit('live_data', {'data': {name: row[m] for m, (name, _) in enumerate(data_types)}})

def decode_config_data(payload):
    chunks = [payload[j:j + chunk_size] for j in range(0, len(payload), chunk_size)]
    row = []
    for k, chunk in enumerate(chunks):
        if k < len(recived_config_data):
            name, data_type = recived_config_data[k]
            value = None
            if data_type == "int":
                value = unpack_int(chunk)
            elif data_type == "uint":
                value = unpack_uint(chunk)
            elif data_type == "float":
                value = unpack_float(chunk)
            row.append(value)
    received_config.append({name: row[m] for m, (name, _) in enumerate(recived_config_data)})
    print(received_config)
    socketio.emit('config_variables', {'data': {name: row[m] for m, (name, _) in enumerate(recived_config_data)}})

# Serial data receiver thread
class DataReceiver(threading.Thread):
    def __init__(self, serial_port, buffer):
        super().__init__()
        self.serial_port = serial_port
        self.buffer = buffer
        self.daemon = True

    def run(self):
        while True:
            data = self.serial_port.read(self.serial_port.in_waiting or 1)
            if data:
                self.buffer.extend(data)

# Flask route to retrieve received data
@app.route('/data', methods=['GET'])
def get_received_data():
    return jsonify(received_data)

# Flask route to update configuration
@app.route('/send', methods=['POST'])
def update_config():
    try:
        config = request.json
        if not config or "type" not in config:
            return jsonify({"error": "Invalid config data or 'type' key missing"}), 400

        if config["type"] == "S":
            print(f"Received config update: {config}")
            data = bytearray([i % 256 for i in range(250)])
            data[0] = ord('S')
            data[1] = ord('\n') 
            send_packet(data)
        
        if config["type"] == "C":
            print(f"MARIO +++ Received config update: {config}")
        
            # Create a bytearray of 250 bytes (as an example, initial filled with 0)
            data = bytearray([i % 256 for i in range(250)])

            # Set the first byte to the packet type (ord('C'))
            data[0] = ord('C')
            
            # Convert ID to 2 bytes and set the second and third bytes
            packet_id = int(config["body"]["id"])
            print(packet_id)
            data[1:3] = struct.pack('!H', packet_id)  # 2-byte unsigned short for ID

            # Set the type byte (for example, 'i' -> ord('i'), 'u' -> ord('u'), etc.)

            # Depending on the type, we need to convert the value to bytes
            value = config["body"]["value"]
            if config["body"]["type"] == "int":  # Integer type
                data[3] = ord('i')
                data[4:8] = struct.pack('<i', int(value))  # 4-byte integer
            elif config["body"]["type"] == "unsigned int":
                data[3] = ord('u')  # Unsigned integer type
                data[4:8] = struct.pack('<I', int(value))  # 4-byte unsigned integer
            elif config["body"]["type"] == "float":  # Float type
                data[3] = ord('f')
                data[4:8] = struct.pack('<f', float(value))  # 4-byte float
            else:
                raise ValueError(f"Unsupported type: {config['body']['type']}")

            # Set the last byte as the delimiter (newline character '\n')
            data[8] = ord('\n')
            print(data)
            # Send the packet
            send_packet(data)
        
        return jsonify({"message": "Config updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

# Start the serial reading and processing
def main():
    global serial_connection
    buffer = bytearray()
    connect_to_serial()

    receiver_thread = DataReceiver(serial_connection, buffer)
    receiver_thread.start()

    try:
        while True:
            process_buffer(buffer)
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("Exiting...")
        serial_connection.close()

# Connect to the serial device
def connect_to_serial():
    global serial_connection
    while serial_connection is None:
        try:
            serial_connection = ser
        except serial.SerialException as e:
            print(f"Failed to connect to the serial port: {e}")
            time.sleep(5)

if __name__ == "__main__":
    # Start Flask and WebSocket server in a separate thread
    threading.Thread(target=lambda: socketio.run(app, host="0.0.0.0", port=SOCKET_PORT), daemon=True).start()

    # Start serial communication
    main()
