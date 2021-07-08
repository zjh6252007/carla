import socket
import tkinter
from threading import Thread
from _thread import *
import datetime
import tkinter as tk
import time


data = "20"
time = "20"
ne = ""

def server():
    
    ip_port = ('127.0.0.1', 8888)
    sk = socket.socket()
    sk.connect(ip_port)
    sk.settimeout(5)
    while True:
        global data
        global time
        global ne
        data = sk.recv(1024).decode()
        sk.send(b"ack")
        time = sk.recv(1024).decode()
        sk.send(b"ack2")
        ne = sk.recv(1024).decode()
    sk.close()

def getmessage():
    global data
    global time
    
    number = int(data)
    if (number >= 0):
        mess = data + " second early"
    else:
        mess = data + " second late"
    var.set(mess)
    root.after(2000, getmessage)
    
def gettime():
    global time
    time_ = int(time)
    if (time_ >= 0):
        mess =   "+"+ time +"kph"
    else:
        mess ="-" + time +"kph"
    var1.set(mess)
    root.after(2000,gettime)

def getnev():
    global ne
    var2.set(ne)
    root.after(2000,getnev)
    
root =tk.Tk()

root.title('mention')

var=tk.StringVar()
var1=tk.StringVar()
var2=tk.StringVar()
color = int(data)

if(color >= 0):
    w =tk.Label(root, text="Hello Python!",textvariable=var,fg='red',font=("微软雅黑",40))
    v =tk.Label(root, text= "hello",textvariable = var1,fg ='red',font=("微软雅黑",40))
    z =tk.Label(root,text="",textvariable = var2,fg='black',font=("微软雅黑",40))
else:
    w =tk.Label(root, text="Hello Python!",textvariable=var,fg='green',font=("微软雅黑",40))
    v =tk.Label(root, text= "hello",textvariable = var1,fg ='green',font=("微软雅黑",40))
    z =tk.Label(root,text="",textvariable = var2, fg='black',font=("微软雅黑",40))

var.set(getmessage())
var1.set(gettime())
var2.set(getnev())
w.pack()
v.pack()
z.pack()
if __name__ == '__main__':
    Thread(target = server).start()
    root.mainloop()
