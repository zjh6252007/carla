import socket
 
s = socket.socket()
host = '127.0.0.1'
port = 15681
 
s.connect((host,port))
 
while True:
    try:
        received = s.recv(1024)#接收的数据类型为str，若传过来的是字典或列表可以用json.loads转换
        print(received)
    except:
        print('error')
