import serial
import time
import threading
import queue

TAG = "GNSS Manager"

class GNSSManager:
    def __init__(self, port : str, baudrate : int = 9600, timeout : float = 0.05) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_connection = None
        self.data_queue = queue.Queue()
        self.running = False
        # the thing is likely to be in 115200 or 921600, others are set in the order of likeliness to be a thing
        self.baudrates = [115200, 921600, 57600, 38400, 19200, 9600, 230400, 460800, 4800, 1200] 

    def connect(self) -> bool:
        
        try:
            self.serial_connection = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            print(TAG, f'Connecting to {self.port} at {self.baudrate} baud...', end='')
            self.running = True
            threading.Thread(target=self.read_serial, daemon=True).start()
            
            if not self.check_connection(timeout = 3):
                print()
                print(TAG, "Hold on, this is not the correct baudrate, let me figure that out for you...")

                detected_baudrate = self.check_baudrate()
                if detected_baudrate == None:
                    self.disconnect()
                    return False
                else:
                    print(TAG, "There you go")
                    return True
            else:
                print(" Connected!")

            return True
        except serial.SerialException as e:
            print(TAG, f'Error connecting: {e}')
            return False

    def disconnect(self) -> bool:
        if self.serial_connection and self.serial_connection.is_open:
            self.running = False
            self.serial_connection.close()
            print(TAG, 'Disconnected.')
        else:
            print(TAG, 'No active connection to disconnect.')

    def send_setting(self, setting : str) -> bool:
        if self.serial_connection and self.serial_connection.is_open:
            setting_with_terminator = setting + '\r\n'
            
            if 'COM COM' in setting:
                print(TAG, setting, end=": ")

                # Check if we do have a connection
                if not self.check_connection():
                    return False
                
                self.data_queue.empty()
                new_baudrate = int(setting.split()[-1])  # Extract the new baudrate

                # Send the command
                self.serial_connection.write(setting_with_terminator.encode())
                time.sleep(0.2)
                old_baudrate = self.baudrate
                
                # well... assume acknowledged, continue
                
                self.change_baudrate(new_baudrate)
                time.sleep(0.2)
                self.data_queue.empty()
                
                # Check connection again
                
                if not self.check_connection(mute=False):
                    self.change_baudrate(old_baudrate)
                    return False

                return True
            
            self.serial_connection.write(setting_with_terminator.encode())
            print(TAG, setting, end=": ")
                
            return self.wait_for_acknowledgment()
        else:
            print(TAG, 'Connection is not open.')
            return False
        
    def send_settings(self, settings : list) -> None:
        for setting in settings:
            self.send_setting(setting)
        
    def send(self, data : bytes) -> None:
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.write(data)
            #print(TAG, f'Sent: {data}')
        else:
            print(TAG, 'Connection is not open.')

    def change_baudrate(self, new_baudrate : int) -> None:
        self.baudrate = new_baudrate
        self.serial_connection.baudrate = new_baudrate
        #print(f'Baud rate changed to: {self.baudrate}')

    def wait_for_acknowledgment(self, mute :bool = False, timeout = 10) -> bool:
        timeout_counter = 0
        while timeout_counter < timeout * 5:  # Wait for a maximum of 10 seconds
            time.sleep(0.2)
            data = self.get_data()
            if data and b'OK!' in data:
                if not mute:
                    print('OK!')
                return True
            timeout_counter += 1
        if not mute:
            print('ERR')
        return False
    
    def check_connection(self, mute : bool = True, timeout : int = 10) -> bool:
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.write("\r\nlog versionb\r\n".encode())
            return self.wait_for_acknowledgment(mute=mute, timeout=timeout)
        else:
            print(TAG, 'Connection is not open.')
            return False

    def read_serial(self) -> None:
        while self.running:
            if self.serial_connection and self.serial_connection.is_open:
                data = self.serial_connection.read(1024)
                if data:
                    self.data_queue.put(data)
            time.sleep(0.05)  # Adjust sleep to manage CPU usage

    def get_data(self) -> bytes:
        try:
            data = self.data_queue.get_nowait()
            #print(data)
            return data # self.data_queue.get_nowait()
        except queue.Empty:
            return None
        
    def check_baudrate(self) -> bool:
        baud_to_skip = self.baudrate
        if self.serial_connection and self.serial_connection.is_open:
            for baud in self.baudrates:
                if baud == baud_to_skip:
                    continue
                try:
                    print(TAG, "Trying", baud)
                    self.data_queue.empty()
                    self.change_baudrate(baud)
                    time.sleep(0.1)
                    
                    if self.check_connection( timeout = 1):
                        print(TAG, f"Device responded at baudrate: {baud}")
                        return baud
                except serial.SerialException:
                    print(TAG, f"Failed to connect at baudrate: {baud}")
                    continue
            print(TAG, "No valid baudrate found.")
            return None
        else:
            print(TAG, 'Connection is not open.')
            return None

