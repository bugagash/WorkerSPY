import threading
import socket
import json
import uuid
from datetime import datetime
from pathlib import Path


class ClientDatabase:
    """Class for interaction with client's database."""
    def __init__(self, db_fname='clients_db.json'):
        self.db_fname = db_fname
        # self.clients_data initialization in load_dataset!
        self.load_database()
    
    def load_database(self):
        """Load database from file."""
        if Path(self.db_fname).exists():
            try:
                with open(self.db_fname, 'r', encoding='utf-8') as f:
                    self.clients_data = json.load(f)
            except:
                self.clients_data = {}
        else:
            self.clients_data = {}
    
    def save_database(self):
        """Save database to file. Rewrites existing file when use."""
        with open(self.db_fname, 'w', encoding='utf-8') as f:
            json.dump(self.clients_data, f, ensure_ascii=False, indent=4)
    
    def create_client(self, client_ip: str) -> str:
        """Get or create client's information from DB.
        ARGS:   client_ip: IP address of client
        Return: Name of client in DB (now IP)
        """
        client_key = client_ip
        if client_key not in self.clients_data:
            # Create new data for client in DB
            self.clients_data[client_key] = {
                'client_id': str(uuid.uuid4()),
                'ip': client_ip,
                'first_seen': datetime.now().isoformat(),
                'last_seen': datetime.now().isoformat(),
                'total_connections': 0,
                'connection_history': []
            }

        return client_key
    
    def update_client_connection(self, client_ip: str, client_port: int, status: str = 'connected') -> None:
        """Update information about client's connetction.
        ARGS:   client_key: unique client's ID, client_port: Port of connected client, status: current connection status
        Return: None
        """
        if client_ip in self.clients_data:
            client_data = self.clients_data[client_ip]
            
            if status == 'connected':
                client_data['last_seen'] = datetime.now().isoformat()
                client_data['total_connections'] += 1
                client_data['current_port'] = client_port
                client_data['status'] = 'online'
                
                # Add connection data to history
                client_data['connection_history'].append({
                    'connected_at': datetime.now().isoformat(),
                    'port': client_port,
                    'disconnected_at': None,
                    'Time_Online': None
                })
            
            elif status == 'disconnected':
                client_data['last_seen'] = datetime.now().isoformat()
                client_data['status'] = 'offline'
                
                # Update disconnection time and Time Online
                if client_data['connection_history']:
                    client_data['connection_history'][-1]['disconnected_at'] = datetime.now().isoformat()
                    
                    TimeDelta = datetime.fromisoformat(client_data['connection_history'][-1]['disconnected_at']) - datetime.fromisoformat(client_data['connection_history'][-1]['connected_at'])
                    client_data['connection_history'][-1]['Time_Online'] = str(TimeDelta)
            
            self.save_database()
    
    def get_client_info(self, client_ip: str):
        return self.clients_data.get(client_ip, None)
    
    def get_connection_history(self, client_ip: str):
        if client_ip in self.clients_data:
            return self.clients_data[client_ip]['connection_history']
        return []

class Server:
    """"Classs for server realisation."""
    def __init__(self):
        self.HOST = '127.0.0.1'
        self.PORT = 8888
        self.clients = [] # Online clients
        self.clients_lock = threading.Lock() # Separate thread to each client
        self.db = ClientDatabase(db_fname='clients_db.json') # DataBase initialization. DB storage in file [db_fname]
        self.server_running = True
        self.server_socket = None
    
    def handle_client(self, client_socket: socket.socket, client_address: tuple[str, str]) -> None:
        """Function for making separate thread for client interaction.
        ARGS:   client_socket: socket of client,
                client_address: tuple['IP', 'PORT'] of client
        Return: None
        """
        client_ip = client_address[0]
        client_port = client_address[1]
        
        # Get information about client or create new
        client_key = self.db.create_client(client_ip)
        client_db_data = self.db.get_client_info(client_key)
        
        # Update client's connection info in database
        self.db.update_client_connection(client_key, client_port, 'connected')
        
        # Current session information
        client_info = {
            'socket': client_socket,
            'address': client_address,
            'ip': client_ip,
            'port': client_port,
            'client_key': client_key,
            'client_id': client_db_data['client_id'],
            'connected_at': datetime.now(),
            'online_before': client_db_data['total_connections'] > 1
        }
        
        with self.clients_lock:
            self.clients.append(client_info)
            print(f"\n[INFO] Averall number of active sessions: {len(self.clients)}\n")
        
        try:
            if client_info['online_before']:
                connection_msg = (
                    f"Connected!\nID: {client_db_data['client_id']}\n"
                    f"IP: {client_ip}:{client_port}\n"
                    f"First connected: {client_db_data['first_seen']}\n"
                    f"Averall connections: {client_db_data['total_connections']}\n"
                    f"Previous connection: {client_db_data['last_seen']}\n"
                )
            else:
                connection_msg = (
                    f"Connected!\nID: {client_db_data['client_id']}\n"
                    f"IP: {client_ip}:{client_port}\n"
                )
            client_socket.send(connection_msg.encode('utf-8'))
            
            curr_client_input = None
            curr_client_message_size = None
            client_message_chunks = []

            # Main session loop. Handeling client's messages
            while self.server_running:
                client_socket.settimeout(1.0)
                message = ""

                try:
                    data = client_socket.recv(4096)
                        
                    if not data:
                        break
                    
                    # Not in receiving process from client
                    if not curr_client_input:
                        message = data.decode('utf-8').strip().split(',')
                        
                        if message[0] not in ["ProcessJSON", "ScreenShot BMP"]:
                            print("\nUnrecognized message from user")
                        else:
                            curr_client_input = message[0]
                            curr_client_message_size = int(message[1])
                    
                    # Receiving Process Information from client
                    elif curr_client_input == "ProcessJSON":
                        message = data.decode('utf-8').strip()
                        client_message_chunks.append(message)
                        client_message = ''.join(client_message_chunks)

                        # End of receiving
                        if len(client_message) == curr_client_message_size - 1 or len(message) < 4096:
                            self.log_client_message(client_db_data['client_id'], client_message)
                            print(f"\nComplete process receiving operation from {client_ip}:{client_port} (ID: {client_db_data['client_id'][:8]}...)")
                            client_message_chunks = []
                            curr_client_input = None
                            curr_client_message_size = None
                    
                    # Receiving screenshoot from client
                    elif curr_client_input == "ScreenShot BMP":
                        # No need to decode. Input -- raw bytes.
                        client_message_chunks.append(data)
                        bytes_read = sum([len(chunk) for chunk in client_message_chunks])
                        
                        if bytes_read == curr_client_message_size or len(data) < 4096:
                            self.save_screenshoot(client_db_data['client_id'], client_message_chunks)
                            print(f"\nComplete screenshoot receiving operation from {client_ip}:{client_port} (ID: {client_db_data['client_id'][:8]}...)")
                            client_message_chunks = []
                            curr_client_input = None
                            curr_client_message_size = None

                    # Response
                    response = f"Server recived: {len(data)} b\n"
                    client_socket.send(response.encode('utf-8'))
                
                except socket.timeout:
                    continue
        
        except ConnectionResetError:
            print("\nClient Disconnected!")
        except OSError as e:
                if getattr(e, 'winerror', None) != 10038:
                    print(f"Error with client {client_ip}:{client_port}: {e}")
        except Exception as e:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Error with {client_ip}:{client_port}: {e}")
        finally:
            # Update connection status in BD
            self.db.update_client_connection(client_key, client_port, 'disconnected')
            
            # Delete client from active client's list
            with self.clients_lock:
                if client_info in self.clients:
                    self.clients.remove(client_info)
            
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Client disconnected {client_ip}:{client_port}")
            print(f"[INFO] Averall online clients: {len(self.clients)}")
            
            try:
                client_socket.close()
            except OSError as e:
                if getattr(e, 'winerror', None) != 10038:
                    print(f"Error with client {client_ip}:{client_port}: {e}")
    
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

    def save_screenshoot(self, client_ID: str, photo_data: list):
        """Function for saving client's screen picture
        ARGS:   client_ID: client's identification ID,
                photo_data: list of chunks given in bytes received from client
        Return: None
        """
        screen_filename = f"screen/{client_ID}_[{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}].bmp"
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
            print(f"Averall active clients: {len(self.clients)}")
            print("=" * 80)
            
            for i, client in enumerate(self.clients, 1):
                uptime = datetime.now() - client['connected_at']
                client_db_data = self.db.get_client_info(client['client_key'])
                
                print(f"{i}.\nIP: {client['ip']}:{client['port']}")
                print(f"ID: {client['client_id']}")
                print(f"Connected at: {client['connected_at'].strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"Time online: {uptime}")
                print("-" * 80)
    
    def show_client_history(self) -> None:
        """All clients history"""
        print("\n" + "=" * 80)
        print("Clients history")
        print("=" * 80)
        
        for i, (_, client_data) in enumerate(self.db.clients_data.items(), 1):
            print(f"{i}.")
            print("-" * 80)
            print(f"ID: {client_data['client_id']}")
            print(f"IP: {client_data['ip']}")
            print(f"Status: {client_data.get('status', 'unknown')}")
            print(f"First online: {client_data['first_seen']}")
            print(f"Last online: {client_data['last_seen']}")
            
            if client_data['connection_history']:
                print(f"\nConnections history (last 5):")
                for conn in client_data['connection_history'][-5:]:
                    print(f"\t+Connected at: {conn['connected_at']}")
                    if conn['disconnected_at']:
                        print(f"\t-Disconnected at: {conn['disconnected_at']}")
                        print(f"\tTime online: {conn['Time_Online']}")
                    else:
                        print(f"\t-Disconnected at: [Now Online]")
                    print("\t" + "-" * 40)
            
            print("-" * 80)

    def send_to_client(self, client_index: int, message: str) -> None:
        """Send command to particular client.
        ARGS:   client_index: 1...N number of connected client, 
                message: message to be sent
        Return: None
        """
        with self.clients_lock:
            if client_index < 1 or client_index > len(self.clients):
                print(f"\nInvalid client\'s number. Avaliable clients: 1-{len(self.clients)}")
                return
            
            client = self.clients[client_index - 1]
            
            try:
                client['socket'].send(message.encode('utf-8'))
                print(f"\nMessage sent to client {client['ip']}:{client['port']}")
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

        if command_option == 1:
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
        AskStatistics = "SEND_STAT"
        AskDeauth = "DEAUTH_REQUEST"
        AskScreen = "SEND_SCREEN"

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
                print(f"\n{client['ip']}:{client['port']} disconnected")
            except Exception as e:
                print(f"\nError while deauth client: {e}")
    
    def disconnect_all_clients(self) -> None:
        """Disconnects all online clients"""
        for i, _ in enumerate(self.clients, 1):
            self.disconnect_client(i)
    
    def start_server(self) -> None:
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Initializing socket
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
            
            accept_thread = threading.Thread(target=accept_clients, daemon=True)
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
