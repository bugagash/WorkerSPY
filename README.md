# Проект: Клиент-Server Python/C++

**Описание**

Клиент-сервер для сбора статистики процессов и скриншотов экрана.

**Файлы проекта**

- `client.cpp`  — C++ клиент на WinAPI (WinSock2, GDI) для Windows
- `server.py` — Python сервер на сокетах для приёма данных

---

## Требования

1. **Клиент (Windows)**

- Компилятор: c++
- Библиотеки:
  - `ws2_32.lib` (WinSock2)
  - `gdi32.lib` (GDI)
  - `user32.lib` (для GetDC/ReleaseDC)

2.  **Сервер (Linux, Windows)**

- Python
- Модули стандартной библиотеки: `socket`, `os`, `datetime`

---

## Сборка и запуск

1. **Клиент (client.cpp)**

```bash
# MSVC
cl client.cpp /EHsc /link ws2_32.lib gdi32.lib user32.lib iphlpapi.lib

# MinGW/GCC
g++ client.cpp -o client.exe -lws2_32 -lgdi32 -liphlpapi
```

Запуск:
```bash
client.exe server_ip server_port [timeout_ms]

# Working example
client.exe 127.0.0.1 8888 30000
```

Параметры: `<server_ip> <server_port> [timeout_ms]`

2. **Сервер (server.py)**

```bash
python serverExample.py
```

Слушает порт 8888. Сохраняет:
- JSON-файлы со статистикой процессов в папку `logs/`
- BMP-файлы скриншотов в папку `screens/`
- JSON-файл с базой данных клиентов (имя по умолчанию `clients_db.json`)

---

## Протокол обмена

1. TCP-соединение.

2. Запросы/сообщения:
   - MAC адресс клиента.
   - JSON со списком процессов
   - Скриншот BMP: сначала 4 байта длины (htonl), затем N байт данных