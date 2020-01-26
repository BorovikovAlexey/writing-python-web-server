import socket

serv_sock = socket.socket(
    socket.AF_INET,  # Задаем семейство протоколов "Интернет"
    socket.SOCK_STREAM,  # Задаем тип передачи данных "Потоковый"
    proto=0,  # Выбираем протоколо "По умолчанию" для TCP. т.е. IP
)

print(type(serv_sock))
print(serv_sock.fileno())

# Вызов bind() заставляет нас указать не только IP адрес, но и порт,
# на котором сервер будет ожидать (слушать) подключения клиентов.
serv_sock.bind(('', 53210))

# 10 - это размер очереди входящих подключений, т.н. backlog
serv_sock.listen(10)

while True:
    # Бесконечно обрабатываем входящие подключения
    client_sock, client_addr = serv_sock.accept()
    print('Connected by', client_addr)

    while True:
        # Пока клиент не отключился, читаем передаваемые
        # им данные и отправляем их обратно
        data = client_sock.recv(1024)
        if not data:
            # Клиент отключился
            print('Connect closed', client_addr)
            break
        client_sock.sendall(f"Вы отправили: {data.decode()}".encode())

    client_sock.close()
