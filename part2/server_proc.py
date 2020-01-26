import os
from typing import Optional
import socket
import sys
import time


def create_server_sock(server_port: int) -> socket.socket:
    server_sock = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
        proto=0,
    )
    server_sock.bind(('', server_port))
    server_sock.listen()
    return server_sock


def accept_client_connect(server_sock: socket.socket, client_id: int) -> socket.socket:
    client_sock, client_address = server_sock.accept()
    print(
        f'Client #{client_id} connected '
        f'{client_address[0]}:{client_address[1]}'
    )
    return client_sock


def handle_request(request):
    # time.sleep(5)
    return request[::-1]


def read_request(client_sock: socket.socket, delimiter: bytes = b'!') -> Optional[bytearray]:
    request = bytearray()
    try:
        while True:
            chunk = client_sock.recv(4)
            if not chunk:
                # Клиент преждевременно отключился.
                return None
            request += chunk
            if delimiter in request:
                return request

    except ConnectionResetError:
        # Соединение было неожиданно разорвано.
        return None
    except Exception:
        raise


def write_response(client_sock: socket.socket, response: bytearray, client_id: int) -> None:
    client_sock.sendall(response)
    client_sock.close()
    print(f'Client #{client_id} has been served')


def serve_client(client_sock: socket.socket, client_id: int) -> Optional[int]:
    child_pid = os.fork()
    if child_pid:
        # Родительский процесс, не делаем ничего
        return child_pid

    # Дочерний процесс:
    #  - читаем запрос
    #  - обрабатываем
    #  - записываем ответ
    #  - закрываем сокет
    #  - завершаем процесс (os._exit())

    request = read_request(client_sock)
    if request is None:
        print(f'Client #{client_id} unexpectedly disconnected')
    else:
        response = handle_request(request)
        write_response(client_sock=client_sock, response=response, client_id=client_id)

    os._exit(0)


def reap_children(active_children: set) -> None:
    for child_pid in active_children.copy():
        active_child_pid, _ = os.waitid(child_pid, os.WNOHANG)
        if active_child_pid:
            active_children.discard(active_child_pid)

    pass


def run_server(port: int = 53210) -> None:
    server_sock = create_server_sock(server_port=port)
    active_children = set()
    client_id = 0
    while True:
        client_socket = accept_client_connect(server_sock=server_sock, client_id=client_id)
        serve_client(client_sock=client_socket, client_id=client_id)
        reap_children(active_children)
        client_id += 1


if __name__ == '__main__':
    run_server(port=int(sys.argv[1]))
