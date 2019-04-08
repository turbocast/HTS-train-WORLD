#!/usr/bin/env python3
#脚本的作用：通过并行提升HTS训练速度
#需要配合修改后的training.pl使用
#作者：hyperzlib
import re
import sys
import threading
import time
import subprocess
import platform

from queue import Queue
#from tkinter import *
from multiprocessing import cpu_count

global shellEncoding

class threadCtrl:
    def __init__(self, threadNum, conf):
        self.config = conf
        self.threadNum = threadNum
        self.finished = []
        self.threadName = list(conf.keys())
        self.threadCommands = list(conf.values())
        self.threadList = []
        self.queue = Queue()
        for i in range(0, len(self.threadName)):
            self.queue.put([self.threadName[i], self.threadCommands[i]])
        self.createThreads()

    def createThreads(self):
        lock = threading.Lock()
        for i in range(0, self.threadNum):
            thread = runShell(i, self.queue, lock)
            self.threadList.append(thread)

    def start(self):
        for i in range(0, self.threadNum):
            self.threadList[i].start()

    def wait(self):
        for i in range(0, self.threadNum):
            self.threadList[i].join()

# class outputWindow(threading.Thread):
    # def __init__(self, threadId):
        # threading.Thread.__init__(self)
        # self.threadId = threadId
        # self.taskName = ""
        # self.buildWindow()

    # def changeTaskName(self, name):
        # self.taskName = name
        # self.window.title("Thread %d [%s]" % (self.threadId, name))
        # self.append("\r\nThread %d starting: %s" % (self.threadId, name))

    # def append(self, str):
        # self.outputText.config(state=NORMAL)
        # self.outputText.insert("end", "\r\n" + str)

    # def buildWindow(self):
        # self.window = Tk()
        # self.window.title("Thread %d" % self.threadId)
        # self.window.geometry('500x400')
        # self.outputText = Text(self.window)
        # self.outputText.config(state=DISABLED)
        # self.outputText.insert("end", "prepareing...")
        # self.outputText.pack()

    # def run(self):
        # self.window.mainloop()


class runShell(threading.Thread):
    def __init__(self, threadId, queue, lock):
        threading.Thread.__init__(self)
        self.threadId = threadId
        self.queue = queue
        self.lock = lock
    
    def run(self):
        global shellEncoding
        #window = outputWindow(self.threadId)
        #window.start()
        while not self.queue.empty():
            config = self.queue.get()
            name = config[0]
            commands = config[1]
            print("Thread %d now starting: %s" % (self.threadId + 1, name))
            #window.changeTaskName(name)
            for command in commands:
                proc = subprocess.Popen(command, bufsize=0, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT) #打开新进程
                sout = proc.stdout
                done = False
                while not done:
                    buffer = str(sout.readline(), shellEncoding)
                    if buffer == "":
                        done = True
                    else:
                        buffer = buffer.rstrip("\r\n")
                        self.lock.acquire()
                        print("[T %d] %s" % (self.threadId + 1, buffer))
                        self.lock.release()



def parseConfig(content):
    lines = content.split("\n")
    comp = re.compile(r'^\[.*?\]')
    nowId = ""
    commandList = {}
    for line in lines:
        line = line.strip()
        if(comp.match(line)):
            nowId = line.strip('[]')
            commandList[nowId] = []
        elif(nowId != "" and line != ""):
            commandList[nowId].append(line)
    return commandList

def loadConfig(file):
    fp = open(file, 'r')
    content = fp.read()
    fp.close()
    return parseConfig(content)

if __name__ == "__main__":
    if len(sys.argv) == 2:
        confFile = sys.argv[1]
    else:
        print("usage: %s <config file>" % sys.argv[0])
        exit(0)

    global shellEncoding
    if platform.system() == "Windows":
        shellEncoding = "cp936"
    else:
        shellEncoding = "utf-8"
    commands = loadConfig(confFile)
    threadNum = cpu_count()
    threadPool = threadCtrl(threadNum, commands)
    threadPool.start()
    threadPool.wait()