import socket

ip_port = ('127.0.0.1', 9999)
sk = socket.socket()
sk.connect(ip_port)
sk.settimeout(5)
data = sk.recv(1024).decode()
print('server:', data)
while True:
    inp = input('player:').strip()
    if not inp:
        continue

    sk.sendall(inp.encode())

    if inp == 'exit':
        print("thank you！")
        break
    data = sk.recv(1024).decode()
    print('server:', data)
sk.close()
