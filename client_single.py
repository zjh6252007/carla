import socket
import tkinter
from threading import Thread
from _thread import *
import datetime
import tkinter as tk
import time


data = "20"
time = "30"
ne = ""
color = "red"
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
        print(data)
        if data == 'None':
            data = "0"
        sk.send(b"ack")
        time = sk.recv(1024).decode()
        if time == "None":
            time = "0"
        sk.send(b"ack2")
        ne = sk.recv(1024).decode()
        sk.send(b"ack3")
    sk.close()
    
    
def getmessage():
    global data
    global color
    number = int(data)
    if (number > 0):
        mess = "increase " + data + "kph"
        colorChangetoRed()
    if(number == 0):
        mess = ''
    if(number < 0):
        number = number * (-1)
        snumber = str(number)
        mess =  "slowdown " + snumber + "kph"
        colorChangetoGreen()
    var.set(mess)
    root.after(1000, getmessage)
    
def gettime():
    global time
    
    time_ = int(time)
    if (time_ > 0):
        mess =    time +"s behind"
    if(time_ == 0):
        mess= ''
    if(time_ < 0):
        mess = time +"s upfront"
    var1.set(mess)
    root.after(1000,gettime)

def getnev():
    global ne
    var2.set(ne)
    root.after(200,getnev)

def colorChangetoRed():
    w.config(fg = 'red')
    v.config(fg = 'red')
    root.update()
def colorChangetoGreen():
    w.config(fg = 'green')
    v.config(fg = 'green')
    root.update()
root =tk.Tk()

root.title('mention')
root.attributes('-topmost',1)
root.resizable(0,0)

var=tk.StringVar()
var1=tk.StringVar()
var2=tk.StringVar()

z =tk.Label(root,text="",textvariable = var2,fg="black",font=("微软雅黑",40))
w =tk.Label(root, text="Hello Python!",textvariable=var1,fg=color,font=("微软雅黑",40))
v =tk.Label(root, text= "hello",textvariable = var,fg =color,font=("微软雅黑",40))

var.set(getmessage())
var1.set(gettime())
var2.set(getnev())

z.pack()
w.pack()
v.pack()
if __name__ == '__main__':
    Thread(target = server).start()
    root.mainloop()
