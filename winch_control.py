import can
import time
import sys
from threading import Thread

# Configuration
DEVICE = "/dev/ttyUSB0"  # Change this to your actual device
CAN_SPEED = 500000       # 500kbps
BAUDRATE = 2000000       # 2Mbps
MOTOR_ID = 1             # Motor ID

def format_can_data(data):
    """Format CAN data as space-separated hex bytes"""
    return " ".join([f"{byte:02X}" for byte in data])

def setup_can_bus():
    """Initialize the CAN bus connection"""
    try:
        bus = can.interface.Bus(
            interface='seeedstudio',
            channel=DEVICE,
            bitrate=CAN_SPEED,
            baudrate=BAUDRATE
        )
        print(f"Connected to CAN bus on {DEVICE}")
        return bus
    except Exception as e:
        print(f"Error setting up CAN bus: {e}")
        sys.exit(1)

def send_message(bus, data, arbitration_id=MOTOR_ID):
    """Send a message with the specified data to the CAN bus"""
    if len(data) != 8:
        print("Error: Message must be exactly 8 bytes")
        return False
    
    message = can.Message(
        arbitration_id=arbitration_id,
        data=data,
        is_extended_id=False
    )
    
    try:
        bus.send(message)
        print(f"Sent message to ID {arbitration_id}: {format_can_data(data)}")
        return True
    except Exception as e:
        print(f"Error sending message: {e}")
        return False

def receive_messages(bus):
    """Continuously receive messages from the CAN bus"""
    print("Listening for CAN messages (Ctrl+C to exit)...")
    try:
        while True:
            message = bus.recv(1)
            if message:
                print(f"Received from ID {message.arbitration_id}: {format_can_data(message.data)}")
    except KeyboardInterrupt:
        print("\nMessage reception stopped")

def parse_byte_string(byte_string):
    """Parse a string of hex bytes like '00 FF 12 34 56 78 9A BC' into bytes"""
    try:
        # Remove any extra whitespace and split by spaces
        parts = byte_string.strip().split()
        
        # Check if we have exactly 8 parts
        if len(parts) != 8:
            print("Error: Please provide exactly 8 bytes")
            return None
        
        # Convert each part to an integer
        data = [int(part, 16) for part in parts]
        return bytes(data)
    except ValueError as e:
        print(f"Error parsing input: {e}")
        return None

def main():
    # Set up CAN bus
    bus = setup_can_bus()
    
    # Start a thread for receiving messages
    receiver_thread = Thread(target=receive_messages, args=(bus,), daemon=True)
    receiver_thread.start()
    
    # Main loop for sending commands
    try:
        while True:
            print("\nEnter 8 bytes as hex values (e.g., '00 00 00 00 00 00 00 00'):")
            byte_string = input("> ")
            
            # Handle special commands
            if byte_string.lower() == 'exit' or byte_string.lower() == 'quit':
                break
                
            data = parse_byte_string(byte_string)
            if data:
                send_message(bus, data)
    
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
    finally:
        print("Closing CAN bus connection...")
        bus.shutdown()

if __name__ == "__main__":
    main()
