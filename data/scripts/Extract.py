#!/bin/python
import sys
import os
import math
import struct
import re
import numpy as np
import statsmodels.api as sm
from progressbar import *
import matplotlib.pyplot as plt
lowess = sm.nonparametric.lowess

def calloc(len):
    ret = []
    for i in range(0, len):
        ret.append(0)
    return ret

def calloc2d(len):
    ret = []
    for i in range(0, len):
        ret.append([0, 0])
    return ret

def smooth(a, WSZ):
    # a:原始数据，NumPy 1-D array containing the data to be smoothed 
    # 必须是1-D的，如果不是，请使用 np.ravel()或者np.squeeze()转化 
    # WSZ: smoothing window size needs, which must be odd number, 
    # as in the original MATLAB implementation
    out0 = np.convolve(a,np.ones(WSZ,dtype=int),'valid')/WSZ
    r = np.arange(1,WSZ-1,2)
    start = np.cumsum(a[:WSZ-1])[::2]/r
    stop = (np.cumsum(a[:-WSZ:-1])[::2]/r)[::-1]
    return np.concatenate(( start , out0, stop ))

def loadVector(filename, width, typeStr):
    fsize = os.path.getsize(filename)
    file = open(filename, 'rb')
    ret = []
    oneByte = 4
    if(typeStr == 'd'):
        oneByte = 8
    length = math.floor(fsize / width / oneByte)
    for i in range(0, length):
        t = file.read(width * oneByte)
        ret.append(struct.unpack(typeStr * width, t))
    file.close()
    return ret

def saveVector(filename, vector, typeStr):
    file = open(filename, 'wb')
    for column in vector:
        if(not isinstance(column, list)):
            file.write(struct.pack(typeStr, column))
        else:
            for one in column:
                file.write(struct.pack(typeStr, one))
    file.close()

def loadLabel(mono, full):
    monoFile = open(mono, 'r')
    fullFile = open(full, 'r')
    monoLines = monoFile.read().split('\n')
    fullLines = fullFile.read().split('\n')
    if(len(monoLines) != len(fullLines)):
        raise Exception("mono label not equal with full label.")
    ret = []
    for i in range(0, len(monoLines)):
        if(monoLines[i] == '' or fullLines[i] == ''):
            continue
        monoData = monoLines[i].split(' ')
        fullData = fullLines[i].split(' ')
        if(len(monoData) != 3 or len(fullData) != 3):
            print("%d, %d" % (len(monoData), len(fullData)))
            raise Exception("label not have enough informations.")
        monoData[0] = float(monoData[0]) / 10e3
        monoData[1] = float(monoData[1]) / 10e3

        t = [monoData[0], monoData[1], monoData[2], fullData[2]]
        ret.append(t)
    return ret

def soprLog(arr):
    ret = []
    for i in range(0, len(arr)):
        t = []
        for j in range(0, len(arr[i])):
            if arr[i][j] <= 0:
                t.append(1e-8)
            else:
                t.append(np.log(arr[i][j]))
        ret.append(t)
    return ret

def soprExp(arr):
    ret = []
    for i in range(0, len(arr)):
        s = []
        for j in range(0, len(arr[i])):
            t = np.exp(arr[i][j])
            if t < 1:
                t = 0
            s.append(t)
        ret.append(s)
    return ret
                

def getNotePitch(note):
    scaList = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']
    scale = scaList.index(note[0:-1]) - 9
    octave = int(note[-1:]) - 4
    targetF0 = 440 * pow(2.0, octave) * pow(2.0, scale / 12.0)
    return targetF0

def getVibrate(f0):
    length = len(f0)
    if length <= 2:
        return
    vib = calloc2d(length) #[vbr, vbp]
    if f0[0] < 0:
        positive = False
    else:
        positive = True

    interPoints = []
    #计算交点
    for i in range(0, length):
        if(positive and f0[i] <= 0):
            interPoints.append(i)
            positive = False
        elif(not positive and f0[i] >= 0):
            interPoints.append(i)
            positive = True
    peak = 0
    period = 0
    for i in range(0, len(interPoints) - 1):
        #计算每一段的深度最大值
        start = interPoints[i]
        end = interPoints[i + 1]
        t = abs(f0[start:end])
        #峰值
        peak = max(t)
        if(peak < 5):
            continue
        #周期
        period = end - start / 2
        for j in range(start, end):
            vib.append([peak, period])
    for i in range(interPoints[-1], length):
        vib.append([peak, period])
    return vib

if __name__ == "__main__":
    if(len(sys.argv) != 3):
        print("Usage: python %s <basename> <frame_period>" % sys.argv[0])
        exit()
    base = sys.argv[1]
    framePeriod = float(sys.argv[2])
    lf0 = 'lf0/%s.lf0' % base
    vib = 'vib/%s.vib' % base
    mono = 'labels/mono/%s.lab' % base
    full = 'labels/full/%s.lab' % base
    
    f0 = soprExp(loadVector(lf0, 1, 'f'))

    fLen = len(f0)
    df0 = calloc2d(fLen)
    df02 = calloc(fLen)
    label = loadLabel(mono, full)
    vibrate = calloc2d(fLen)
    lLen = len(label)

    widgets = ['Extract VIB: ',Percentage(), ' ', Bar('#'), ' ']
    pbar = ProgressBar(widgets = widgets).start()
    for i in range(0, lLen):
        pbar.update((i / lLen) * 100)
        start = max(math.floor(label[i][0] / framePeriod), 0)
        end = min(math.floor(label[i][1] / framePeriod), fLen)
        notePitch = re.findall(r'/E:\w+\]', label[i][3])[0]
        notePitch = notePitch.replace('/E:', '').replace(']', '')
        basePitch = 0
        if(notePitch != 'xx'):
            #print(notePitch)
            basePitch = getNotePitch(notePitch)
        #计算差分f0
        for j in range(start, end):
            t = f0[j][0] - basePitch + 500
            if t <= 0:
                t = -1
            df0[j][0] = f0[j][0]
            if(f0[j][0] < 55.0):
                df0[j][1] = 0
                df02[j] = 0
            else:
                df0[j][1] = t
                df02[j] = f0[j][0] - basePitch
        #计算颤音
        #先把前后为0的区域trim掉，再根据中间的0切分
        j = start
        while j < end:
            ostart = j
            oend = 0
            firstTime = True
            while j < end:
                if firstTime and f0[j][0] >= 55.0:
                    #标记开始时间
                    ostart = j
                    firstTime = False
                elif not firstTime and f0[j][0] < 55.0:
                    oend = j
                    break
                j += 1
            if oend == 0:
                continue
            #print("start: %d, end: %d" % (ostart, oend))
            if(oend - ostart > 20):
                #有数据的部分
                pf0 = np.array(df02[ostart:oend])
                keys = range(0, len(pf0))
                s = lowess(pf0, keys, it = 20, delta = 0.0)
                pf0 = pf0 - s[:, 1]
                t = getVibrate(pf0)
                for k in range(0, len(t)):
                    vibrate[ostart + k][0] = t[k][0]
                    vibrate[ostart + k][1] = t[k][1]
    saveVector(lf0, soprLog(df0), 'f')
    saveVector(vib, soprLog(vibrate), 'f')
    pbar.finish()