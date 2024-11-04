import socket
import struct
import time
import csv

HOST = '0.0.0.0'  # Listen on all available network interfaces
PORT = 5000       # Port number matching the ESP32 code
PACKET_SIZE = 10  # 5 values * 2 bytes (16 bits each)

def start_server():
    # Open CSV file for appending data
    with open("received_data.csv", mode="a", newline="") as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(["Value1", "Value2", "Value3", "Value4", "Value5"])  # Header row

        # Create a TCP socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.bind((HOST, PORT))
            server_socket.listen()
            print(f"Server listening on {HOST}:{PORT}")

            while True:
                # Wait for a client connection
                print("Waiting for a new client connection...")
                conn, addr = server_socket.accept()
                with conn:
                    print(f"Connected by {addr}")
                    
                    # Set a timeout for recv to detect connection loss
                    conn.settimeout(1.0)

                    while True:
                        start_time = time.time()  # Capture start time for 20 Hz timing

                        try:
                            # Receive the packet
                            data = conn.recv(PACKET_SIZE)
                            if not data:
                                print(f"Client {addr} disconnected")
                                break  # Client disconnected

                            # Unpack the data (assuming each value is a 16-bit unsigned integer)
                            values = struct.unpack('<5h', data)
                            print("Received data:", values)

                            # Write the received values to the CSV file
                            csv_writer.writerow(values)

                        except socket.timeout:
                            # Handle timeout (no data received within the timeout)
                            print("No data received within timeout period. Reconnecting...")
                            break  # Exit the inner loop to accept a new connection

                        except socket.error as e:
                            print(f"Socket error: {e}")
                            break

                        # Maintain a fixed 20 Hz rate
                        elapsed_time = time.time() - start_time
                        time_to_wait = max(0, 0.05 - elapsed_time)  # 0.05 sec (50 ms) for 20 Hz
                        time.sleep(time_to_wait)

if __name__ == "__main__":
    start_server()
