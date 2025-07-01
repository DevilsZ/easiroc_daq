import socket

HOST = '192.168.10.17'  # 機器のIPアドレス
PORT = 24               # 正しいポートに変更

try:
    with socket.create_connection((HOST, PORT), timeout=5) as sock:
        print('Connected to device.')

        # 必要に応じて送信コマンドを指定（例: '*IDN?\n'）
        sock.sendall(b'*IDN?\n')  # または正しいプロトコルで必要なコマンドに変更
        response = sock.recv(1024)
        print('Received:', response.decode(errors='ignore'))

except Exception as e:
    print('Error:', e)
