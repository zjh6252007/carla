import socket
import socketserver
import time
import threading
from socketserver import BaseRequestHandler,ThreadingTCPServer


second = 2
class MyServer(socketserver.BaseRequestHandler):
 
    def handle(self):
         while True:
             client = self.request
             print('客户已链接')
             #buf = client.recv(1024)
             #print('接收到的',buf)
             try:
                 client.send("Speed up")
                 time.sleep(second)#要发送的数据，类型为str。若要发送字典、列表可以用json.dumps转换
             except:
                 print('socket.error')
                 return

if __name__ == '__main__':
    HOST = '127.0.0.1'
    PORT = 15681
    ADDR = (HOST,PORT)
    server = ThreadingTCPServer(ADDR,MyServer)  #参数为监听地址和已建立连接的处理类
    print('listening')
    server.serve_forever()  #监听，建立好TCP连接后，为该连接创建新的socket和线程，并由处理类中的handle方法处理
    print(server)

