import threading
import socket
import json
from datetime import datetime
from pathlib import Path


class ClientDatabase:
    """Class for interaction with client's database."""
    def __init__(self, db_fname='clients_db.json'):
        self.db_fname = db_fname
        self.load_database()
    
    def load_database(self) -> dict:
        """Load database from file."""
        if Path(self.db_fname).exists():
            try:
                with open(self.db_fname, 'r', encoding='utf-8') as f:
                    self.clients_data = json.load(f)
            except:
                self.clients_data = {}
        else:
            self.clients_data = {}
    
    def save_database(self) -> None:
        """Save database to file. Rewrites existing file when use."""
        with open(self.db_fname, 'w', encoding='utf-8') as f:
            json.dump(self.clients_data, f, ensure_ascii=False, indent=4)
    
    def create_client(self, client_mac: str) -> None:
        """Create client's information block in DB if needed.
        
        ARGS:   client_mac: MAC address of a client
        Return: None
        """
        if client_mac not in self.clients_data:
            # Create new data for client in DB
            self.clients_data[client_mac] = {
                'mac': client_mac,
                'ip': None,
                'port': None,
                'first_seen': datetime.now().isoformat(),
                'last_seen': datetime.now().isoformat(),
                'total_connections': 0,
                'connection_history': []
            }
    
    def update_client_connection(self, client_mac: str, client_ip: str, client_port: int, status: str = 'connected') -> None:
        """Update information about client's connetction.
        
        ARGS:   client_key: unique client's ID,
                client_port: Port of connected client,
                status: ['connected', 'disconnected'] current connection status
        Return: None
        """
        if client_mac in self.clients_data:
            client_data = self.clients_data[client_mac]
            
            if status == 'connected':
                client_data['last_seen'] = datetime.now().isoformat()
                client_data['total_connections'] += 1
                client_data['ip'] = client_ip
                client_data['port'] = client_port
                client_data['status'] = 'online'
                client_data['connection_history'].append({
                    'connected_at': datetime.now().isoformat(),
                    'ip': client_ip,
                    'port': client_port,
                    'disconnected_at': None,
                    'Time_Online': None
                })
            
            elif status == 'disconnected':
                client_data['last_seen'] = datetime.now().isoformat()
                client_data['status'] = 'offline'

                if client_data['connection_history']:
                    client_data['connection_history'][-1]['disconnected_at'] = datetime.now().isoformat()
                    TimeDelta = datetime.fromisoformat(client_data['connection_history'][-1]['disconnected_at']) - datetime.fromisoformat(client_data['connection_history'][-1]['connected_at'])
                    client_data['connection_history'][-1]['Time_Online'] = str(TimeDelta)
            
            self.save_database()
    
    def get_client_info(self, client_mac: str) -> dict:
        return self.clients_data.get(client_mac, None)
    
    def get_connection_history(self, client_mac: str) -> list:
        if client_mac in self.clients_data:
            return self.clients_data[client_mac]['connection_history']
        return []

class Server:
    """"Classs for server realisation."""
    def __init__(self):
        self.HOST = '127.0.0.1'
        self.PORT = 8888
        self.clients = []
        self.clients_lock = threading.Lock()
        self.server_commands = ["SEND_STAT", "SEND_SCREEN", "DEAUTH_REQUEST"]
        self.db = ClientDatabase(db_fname='clients_db.json')
        self.server_running = True
        self.server_socket = None
    
    def handle_client(self, client_socket: socket.socket, client_address: tuple[str, str]) -> None:
        """Function for making 
        
        ARGS:   client_socket: socket of client,
                client_address: tuple['IP', 'PORT'] of client
        Return: None
        """
        client_ip = client_address[0]
        client_port = client_address[1]
        client_mac = None
        
        try:
            mac_message = "SEND_MAC"
            client_socket.send(mac_message.encode('utf-8'))
            data = client_socket.recv(4096)
            message = data.decode('utf-8').strip().split(',')
            
            if message[0] == "MAC_ADDRESS":
                data = client_socket.recv(1024)
                message = data.decode('utf-8').strip()
                client_mac = message
        except Exception as e:
            print(f"\nEncountered [{client_mac}]: [{e}]\n")
            return

        self.db.create_client(client_mac)
        client_db_data = self.db.get_client_info(client_mac)
        client_info = {
            'socket': client_socket,
            'ip': client_ip,
            'port': client_port,
            'mac': client_mac,
            'connected_at': datetime.now(),
            'online_before': client_db_data['total_connections'] > 1
        }

        if client_info['mac'] in [client['mac'] for client in self.clients]:
            deauth_message = "DEAUTH_REQUEST"
            client_socket.send(deauth_message.encode('utf-8'))
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Attempting multiple connection {client_mac} ({client_ip}:{client_port})")
            return
        
        self.db.update_client_connection(client_mac, client_ip, client_port, 'connected')
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Connected: {client_mac} ({client_ip}:{client_port})")

        with self.clients_lock:
            self.clients.append(client_info)

        try:
            client_input_command = None # ["ProcessJSON", "ScreenShot BMP"]
            client_message_chunks = [] # Get client's big data by 4096 bytes chunks if needed
            client_message_size = None
            receiving_size = 1 # Receive message by 1 byte until '\n' read

            while self.server_running:
                client_socket.settimeout(1.0)

                try:
                    data = client_socket.recv(receiving_size)
                        
                    if not data:
                        break
                    
                    # Not in receiving process from client
                    if not client_input_command:
                        chunk = data.decode('utf-8')
                        client_message_chunks.append(chunk)
                        
                        if chunk == '\n':
                            message = "".join(client_message_chunks).split(',') # Expected <"CommandName", "Message size">
                            if message[0] not in ["ProcessJSON", "ScreenShot BMP"]:
                                print(f"[{datetime.now().strftime('%H:%M:%S')}] Unrecognized message {client_mac} ({client_ip}:{client_port})")
                            else:
                                client_input_command = message[0]
                                client_message_size = int(message[1])
                                client_message_chunks = []
                                receiving_size = 4096

                    # Receiving Process Information from client
                    elif client_input_command == "ProcessJSON":
                        message = data.decode('utf-8')
                        client_message_chunks.append(message)
                        client_message = ''.join(client_message_chunks)
                        receiving_size = min(4096, client_message_size - len(client_message))
                        
                        if len(client_message) == client_message_size:
                            filename = client_db_data['mac'].replace(':', '_')
                            self.log_client_message(filename, client_message)
                            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Received running processes from client {client_mac} ({client_ip}:{client_port})\n")
                            
                            client_message_chunks = []
                            client_input_command = None
                            client_message_size = None
                            receiving_size = 1

                    # Receiving screenshot from client
                    elif client_input_command == "ScreenShot BMP":
                        client_message_chunks.append(data)
                        bytes_read = sum([len(chunk) for chunk in client_message_chunks])
                        receiving_size = min(4096, client_message_size - bytes_read)

                        if bytes_read == client_message_size:
                            filename = client_db_data['mac'].replace(':', '_')
                            self.save_screenshoot(filename, client_message_chunks)
                            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Received screenshot from client {client_mac} ({client_ip}:{client_port})\n")
                            
                            client_message_chunks = []
                            client_input_command = None
                            client_message_size = None
                            receiving_size = 1
                
                except socket.timeout:
                    continue

        except ConnectionResetError:
            print("\nClient Disconnected!")
        except OSError as e:
                if getattr(e, 'winerror', None) != 10038:
                    print(f"\nError with:{client_mac} ({client_ip}:{client_port}) [{e}]")
        except Exception as e:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Error with: {client_mac} ({client_ip}:{client_port}): {e}")
        
        finally:
            self.db.update_client_connection(client_mac, client_ip, client_port, 'disconnected')

            with self.clients_lock:
                if client_info in self.clients:
                    self.clients.remove(client_info)

            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Disconnected: {client_mac} ({client_ip}:{client_port})")

            try:
                client_socket.close()
            except OSError as e:
                if getattr(e, 'winerror', None) != 10038:
                    print(f"Error with client {client_mac} ({client_ip}:{client_port}): {e}")

    def log_client_message(self, client_ID: str, message: str) -> None:
        """Function for logging client's message to log file.
        
        ARGS:   client_ID: client's identification ID,
                message: client's message to log
        Return: None
        """
        log_filename = f"logs/{client_ID}.txt"
        Path("logs").mkdir(exist_ok=True)
        
        with open(log_filename, 'a', encoding='utf-8') as log:
            log.write(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]\n{message}\n")

    def save_screenshoot(self, client_mac: str, photo_data: list) -> None:
        """Function for saving client's screen picture
        
        ARGS:   client_mac: client's MAC address,
                photo_data: list of chunks given in bytes received from client
        Return: None
        """
        screen_filename = f"screen/{client_mac}_[{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}].bmp"
        Path("screen").mkdir(exist_ok=True)

        with open(screen_filename, 'wb') as photo:
            for photo_chunk in photo_data:
                photo.write(photo_chunk)

    def show_menu(self) -> None:
        """Showing server controll menu"""
        print("\n" + "=" * 60)
        print("Server control menu")
        print("=" * 60)
        print("1. Show active clients")
        print("2. Show clients history")
        print("3. Send command to client")
        print("4. Send command to all clients")
        print("5. Disconnect client")
        print("6. Disconnect all clients")
        print("0. Stop server")
        print("=" * 60)

    def show_command_option(self) -> None:
        """Showing command option, client can accept"""
        print("\n" + "=" * 60)
        print("Options:")
        print("1. Ask client\'s running process statistics")
        print("2. Ask user\'s screen capture")
        print("3. Ask client to deauth")
        print("=" * 60)

    def menu_loop(self) -> None:
        """Server control section"""
        while self.server_running:
            try:
                self.show_menu()
                choice = input("\nChoose action: ").strip()
                
                # List all clients
                if choice == '1':
                    self.list_clients()
                
                # List all clients with information
                elif choice == '2':
                    self.show_client_history()
                
                # Send command to client
                elif choice == '3':
                    self.list_clients()
                    
                    try:
                        client_num = int(input("\nEnter Client\'s number: "))
                        self.show_command_option()
                        command_num = int(input("Enter command: "))
                        self.send_Command_to_client(client_num, command_num)
                    except ValueError:
                        print("Invalid number format")
                
                # Send command to all clients
                elif choice == '4':
                    self.show_command_option()
                    option_num = int(input("\nChoose command for all users (0 to exit): "))
                    
                    if (option_num == 0):
                        continue
                    self.send_Command_to_all(option_num)
                
                # Disconnect client
                elif choice == '5':
                    self.list_clients()

                    try:
                        client_num = int(input("\nEnter Client\'s number to disconnect: "))
                        self.disconnect_client(client_num)
                    except ValueError:
                        print("Invalid number format")

                # Disconnect all clients
                elif choice == '6':
                    self.disconnect_all_clients()

                # Server interruption
                elif choice == '0':
                    confirm = input("\nEnterupt server? (yes/no): ").lower()
                    
                    if confirm in ['yes', 'y', 'да']:
                        print("\nStopping server...")
                        self.disconnect_all_clients()
                        self.server_running = False
                        break
                
                else:
                    print("\nInvalid choise. Try again")
            
            except KeyboardInterrupt:
                print("\n\nStopping server...")
                self.server_running = False
                break
            except Exception as e:
                print(f"\nError in menu section: {e}")
    
    def list_clients(self) -> None:
        """All connected clients list"""
        with self.clients_lock:
            if not self.clients:
                print("No active clients")
                return
            
            print("\n" + "=" * 80)
            print(f"Number of active clients: {len(self.clients)}")
            print("-" * 80)
            
            for i, client in enumerate(self.clients, 1):
                uptime = datetime.now() - client['connected_at']
                print(f"{i}. {client['mac']}\n")
                print(f"MAC: {client['mac']}")
                print(f"IP: {client['ip']}:{client['port']}")
                print(f"Connected at: {client['connected_at'].strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"Time online: {uptime}")
                print("-" * 80)
            print("=" * 80)
    
    def show_client_history(self) -> None:
        """All clients history"""
        print("\n" + "=" * 80)
        print(f"Clients history. Total: [{len(self.db.clients_data)}] clients.")
        print("-" * 80)
        
        for i, (_, client_data) in enumerate(self.db.clients_data.items(), 1):
            print(f"{i}. {client_data['mac']}\n")
            print(f"MAC: {client_data['mac']}")
            print(f"IP: {client_data['ip']}:{client_data['port']}")
            print(f"First online: {client_data['first_seen']}")
            print(f"Last online: {client_data['last_seen']}")
            print(f"Status: {client_data.get('status', 'unknown')}")
            
            if client_data['connection_history']:
                print(f"\nConnections history (last 3):")
                for conn in client_data['connection_history'][-3:]:
                    print(f"\t+Connected at: {conn['connected_at']}")
                    if conn['disconnected_at']:
                        print(f"\t-Disconnected at: {conn['disconnected_at']}")
                        print(f"\tTime online: {conn['Time_Online']}")
                    else:
                        print(f"\t-Disconnected at: [Online]")
                    print("\t" + "-" * 40)
            
            print("-" * 80)

    def send_to_client(self, client_index: int, message: str) -> None:
        """Send command to particular client.
        
        ARGS:   client_index: 1...N number of connected client, 
                message: message to be sent
        Return: None
        """
        with self.clients_lock:
            if not self.clients:
                print("No active clients")
                return
            if client_index < 1 or client_index > len(self.clients):
                print(f"\nInvalid client\'s number. Avaliable clients: 1-{len(self.clients)}")
                return
            
            client = self.clients[client_index - 1]
            
            try:
                client['socket'].send(message.encode('utf-8'))
            except Exception as e:
                print(f"\nSending Error: {e}")
    
    def send_Command_to_client(self, client_index: int, command_option: int) -> None:
        """Wrap between send_to_client and user. Allows to send coorect codes to manipulate client's behaviour.
        
        ARGS:   client_index: number of client,
                command_option: Choosed allowed option to send.
        Return: None
        """
        AskStatistics = "SEND_STAT"
        AskDeauth = "DEAUTH_REQUEST"
        AskScreen = "SEND_SCREEN"
        AskMac = "SEND_MAC"

        if command_option == 0:
            self.send_to_client(client_index, AskMac)
        elif command_option == 1:
            self.send_to_client(client_index, AskStatistics)
        elif command_option == 2:
            self.send_to_client(client_index, AskScreen)
        elif command_option == 3:
            self.send_to_client(client_index, AskDeauth)
    
    def send_Command_to_all(self, command_option: int) -> None:
        """Same wrap as send_command_to_client.
        
        ARGS:   command_option: number of command to be sent.
        Return: None
        """
        for client_index, _ in enumerate(self.clients, 1):
            self.send_Command_to_client(client_index, command_option)
    
    def disconnect_client(self, client_index: int) -> None:
        """Disconnects one client"""
        with self.clients_lock:
            if client_index < 1 or client_index > len(self.clients):
                print(f"\nInvalid client number")
                return
            
            client = self.clients[client_index - 1]
            try:
                client['socket'].close()
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Disconnected: {client['mac']} ({client['ip']}:{client['port']})")
            except Exception as e:
                print(f"\nError while deauth: {client['mac']} ({client['ip']}:{client['port']}) | {e}")
    
    def disconnect_all_clients(self) -> None:
        """Disconnects all online clients"""
        for i, _ in enumerate(self.clients, 1):
            self.disconnect_client(i)
    
    def start_server(self) -> None:
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server_socket.bind((self.HOST, self.PORT))
            self.server_socket.listen(5)
            
            print("=" * 60)
            print(f"Server started at {self.HOST}:{self.PORT}")
            print(f"Starting time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 60)
            
            def accept_clients():
                while self.server_running:
                    try:
                        self.server_socket.settimeout(1.0)
                        client_socket, client_address = self.server_socket.accept()
                        
                        client_thread = threading.Thread(
                            target=self.handle_client,
                            args=(client_socket, client_address),
                            daemon=True
                        )
                        client_thread.start()
                    
                    except socket.timeout:
                        continue
                    except Exception as e:
                        if self.server_running:
                            print(f"\nError while handaling client: {e}")
            
            accept_thread = threading.Thread(target=accept_clients, daemon=True, name="AcceptClients")
            accept_thread.start()
            
            self.menu_loop()
        
        except OSError as e:
            print(f"\nServer Error: {e}")
        except Exception as e:
            print(f"\nCritical Server Error: {e}")
        finally:
            self.server_running = False
            
            with self.clients_lock:
                for client in self.clients[:]:
                    try:
                        client['socket'].close()
                    except:
                        pass
            
            if self.server_socket:
                self.server_socket.close()
            
            print("\n" + "=" * 60)
            print("Server completely stopped")
            print("=" * 60)


if __name__ == "__main__":
    server = Server()
    server.start_server()
