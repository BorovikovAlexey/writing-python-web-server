import io
import socket
import sys

MAX_LINE = 64 * 1024


class Request:
    def __init__(self, *, method: str, target: str, version: str, rfile: io.BufferedReader) -> None:
        self.method = method
        self.target = target
        self.version = version
        self.rfile = rfile


class MyHTTPServer:
    def __init__(self, host: str, port: int, server_name: str) -> None:
        self._host = host
        self._port = port
        self._server_name = server_name

    def server_forever(self) -> None:
        server_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM,
            proto=0,
        )
        try:
            server_socket.bind((self._host, self._port))
            server_socket.listen()

            while True:
                connect, _ = server_socket.accept()
                try:
                    self.server_client(connect)
                except Exception as error:
                    print("Client server failed", error)
        finally:
            server_socket.close()

    def server_client(self, connect: socket.socket) -> None:
        try:
            request = self.parse_request(connect)
            response = self.handle_request(request)
            self.send_response(response)

        except ConnectionResetError:
            connect = None
        except Exception as error:
            self.send_error(connect, error)

        if connect:
            connect.close()

    def parse_request(self, connect: socket.socket) -> Request:
        rfile = connect.makefile(mode='rb')
        raw = rfile.readline(size=MAX_LINE + 1)  # эффективно читаем строку целиком
        if len(raw) > MAX_LINE:
            raise Exception('Request line is too long')

        req_line = str(raw, 'iso-8859-1')
        req_line = req_line.rstrip('\r\n')
        words = req_line.split()  # разделяем по пробелу
        if len(words) != 3:  # и ожидаем ровно 3 части
            raise Exception('Malformed request line')

        method, target, version = words
        if version != 'HTTP/1.1':
            raise Exception('Unexpected HTTP version')

        return Request(method=method, target=target, version=version, rfile=rfile)

    def send_error(self, connect: socket.socket, error: str) -> None:
        pass

    def handle_request(self, request: Request) -> None:
        pass

    def send_response(self, response: str) -> None:
        pass


if __name__ == '__main__':
    host = sys.argv[1]
    port = int(sys.argv[2])
    name = sys.argv[3]

    server = MyHTTPServer(host, port, name)
    try:
        server.server_forever()
    except KeyboardInterrupt:
        pass
