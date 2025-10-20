# Проект: Клиент-Server Python/C++

**Описание**

Клиент-сервер для сбора статистики процессов и скриншотов экрана.

**Файлы проекта**

- `client.cpp`  — C++ клиент на WinAPI (WinSock2, GDI) для Windows
- `server.py` — Python сервер на сокетах для приёма данных
- `README.md`   — этот файл

---

## Требования

### Клиент (Windows)
- Компилятор: MSVC 2019+ или MinGW/GCC с поддержкой C++17
- Библиотеки:
  - `ws2_32.lib` (WinSock2)
  - `gdi32.lib` (GDI)
  - `user32.lib` (для GetDC/ReleaseDC)

### Сервер (Linux, Windows)
- Python 3.6+
- Модули стандартной библиотеки: `socket`, `os`, `uuid`, `datetime`

---

## Сборка и запуск

### Клиент (C++)

```bash
# MSVC (Developer Command Prompt)
cl client.cpp /EHsc /link ws2_32.lib gdi32.lib user32.lib

# MinGW/GCC
g++ client.cpp -o client.exe -lws2_32 -lgdi32
```

Запуск:
```bash
client.exe server_ip server_port [timeout_ms]

# Working example
client.exe 127.0.0.1 8888 30000
```
Параметры: `<server_ip> <server_port> [timeout_ms]`

### Сервер (Python)

```bash
python serverExample.py
```
Слушает порт 8888. Сохраняет:
- JSON-файлы со статистикой процессов в папку `logs/`
- BMP-файлы скриншотов в папку `screens/`

---

## Протокол обмена

1. TCP-соединение.
2. Запросы/сообщения:
   - JSON со списком процессов
   - Скриншот BMP: сначала 4 байта длины (htonl), затем N байт данных
