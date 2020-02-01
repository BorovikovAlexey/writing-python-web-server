import email
import io
import json
import socket
import sys
from email.parser import Parser
from functools import lru_cache
from typing import Any, Tuple
from urllib.parse import parse_qs, urlparse

MAX_LINE = 64 * 1024
MAX_HEADERS = 100


class Response:
    def __init__(self, status: int, reason: Any, headers=None, body=None):
        self.status = status
        self.reason = reason
        self.headers = headers
        self.body = body


class Request:
    def __init__(
            self,
            *,
            method: str,
            target: str,
            version: str,
            headers: email.message.Message,
            rfile: io.BufferedReader,
    ) -> None:
        self.method = method
        self.target = target
        self.version = version
        self.headers = headers
        self.rfile = rfile

    @property
    def path(self):
        return self.url.path

    @property
    @lru_cache(maxsize=None)
    def query(self):
        return parse_qs(self.url.query)

    @property
    @lru_cache(maxsize=None)
    def url(self):
        return urlparse(self.target)

    def body(self):
        size = self.headers.get('Content-Length')
        if not size:
            return None
        return self.rfile.read(size)


class HTTPError(Exception):
    def __init__(self, status, reason, body=None):
        super()
        self.status = status
        self.reason = reason
        self.body = body


class MyHTTPServer:
    def __init__(self, host: str, port: int, server_name: str) -> None:
        self._host = host
        self._port = port
        self._server_name = server_name
        self._users = {}

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
            self.send_response(connect=connect, response=response)

        except ConnectionResetError:
            connect = None
        except Exception as error:
            self.send_error(connect, error)

        if connect:
            connect.close()

    def parse_request(self, connect: socket.socket) -> Request:
        rfile = connect.makefile(mode='rb')
        method, target, version = self.parse_request_line(rfile)
        headers = self.parse_headers(rfile)

        host = headers.get('Host')
        if not host:
            raise HTTPError(400, 'Bad request')
        if host not in (self._server_name, f'{self._server_name}:{self._port}'):
            raise HTTPError(404, 'Not found')

        return Request(method=method, target=target, version=version, headers=headers, rfile=rfile)

    def parse_request_line(self, rfile: io.BufferedReader) -> Tuple[str, str, str]:
        raw = rfile.readline(MAX_LINE + 1)  # эффективно читаем строку целиком
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

        return method, target, version

    def parse_headers(self, rfile: io.BufferedReader) -> email.message.Message:
        headers = []
        while True:
            line = rfile.readline(MAX_LINE + 1)
            if len(line) > MAX_LINE:
                raise Exception('Header line is too long')

            if line in (b'\r\n', b'\n', b''):
                # завершаем чтение заголовков
                break

            headers.append(line)
            if len(headers) > MAX_HEADERS:
                raise Exception('Too many headers')

        sheaders = b''.join(headers).decode('iso-8859-1')
        return Parser().parsestr(sheaders)

    def send_error(self, connect: socket.socket, error: HTTPError) -> None:
        try:
            status = error.status
            reason = error.reason
            body = (error.body or error.reason).encode('utf-8')
        except:
            status = 500
            reason = b'Internal Server Error'
            body = b'Internal Server Error'
        response = Response(status, reason,
                            [('Content-Length', len(body))],
                            body)
        self.send_response(connect=connect, response=response)

    def handle_request(self, request: Request) -> None:
        if request.path == '/users' and request.method == 'POST':
            return self.handle_post_users(request)

        if request.path == '/users' and request.method == 'GET':
            return self.handle_get_users(request)

        if request.path.startswith('/users/'):
            user_id = request.path[len('/users/'):]
            if user_id.isdigit():
                return self.handle_get_user(request, user_id)

        raise Exception('Not found')

    def handle_post_users(self, request: Request):
        user_id = len(self._users) + 1
        self._users[user_id] = {'id': user_id,
                                'name': request.query['name'][0],
                                'age': request.query['age'][0]}
        return Response(204, 'Created')

    def handle_get_users(self, request: Request):
        accept = request.headers.get('Accept')
        if 'text/html' in accept:
            contentType = 'text/html; charset=utf-8'
            body = '<html><head></head><body>'
            body += f'<div>Пользователи ({len(self._users)})</div>'
            body += '<ul>'
            for u in self._users.values():
                body += f'<li>#{u["id"]} {u["name"]}, {u["age"]}</li>'
            body += '</ul>'
            body += '</body></html>'

        elif 'application/json' in accept:
            contentType = 'application/json; charset=utf-8'
            body = json.dumps(self._users)

        else:
            # https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/406
            return Response(406, 'Not Acceptable')

        body = body.encode('utf-8')
        headers = [('Content-Type', contentType),
                   ('Content-Length', len(body))]
        return Response(200, 'OK', headers, body)

    def handle_get_user(self, request: Request, user_id: int):
        pass

    def send_response(self, *, connect: socket.socket, response: Response) -> None:
        wfile = connect.makefile('wb')
        status_line = f'HTTP/1.1 {response.status} {response.reason}\r\n'
        wfile.write(status_line.encode('iso-8859-1'))

        if response.headers:
            for (key, value) in response.headers:
                header_line = f'{key}: {value}\r\n'
                wfile.write(header_line.encode('iso-8859-1'))

        wfile.write(b'\r\n')

        if response.body:
            wfile.write(response.body)

        wfile.flush()
        wfile.close()


if __name__ == '__main__':
    host = sys.argv[1]
    port = int(sys.argv[2])
    name = sys.argv[3]

    server = MyHTTPServer(host, port, name)
    try:
        server.server_forever()
    except KeyboardInterrupt:
        pass
