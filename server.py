import socketserver
import json
import time

CV_message={"carla0":{"advice speed": -10, "time difference": 3, "navigation": "go straight"},"carla1":{}, "carla2":{}}
adspeed = str(CV_message['carla0']['advice speed'])
td = str(CV_message['carla0']['time difference'])
na = CV_message['carla0']['navigation']

#adspeed2 = str(CV_message['carla1']['advice speed'])
#td2 = str(CV_message['carla1']['time difference'])
#na2 = CV_message['carla1']['navigation']

#adspeed3 = str(CV_message['carla2']['advice speed'])
#td3 = str(CV_message['carla2']['time difference'])
#na3 = CV_message['carla2']['navigation']
class MyServer(socketserver.BaseRequestHandler):

    def handle(self):
        conn = self.request
        address = self.client_address
        while True:
            print(address)
            cpeed = adspeed
            ctd = td
            cna = na
            time.sleep(1)
            conn.sendall(cpeed.encode('utf-8'))
            ack = conn.recv(1024)
            print(ack)
            conn.sendall(ctd.encode('utf-8'))
            ack2 = conn.recv(1024)
            print(ack2)
            conn.sendall(cna.encode('utf-8'))
if __name__ == '__main__':
    server = socketserver.ThreadingTCPServer(('127.0.0.1', 8888), MyServer)
    print("start")
    server.serve_forever()
