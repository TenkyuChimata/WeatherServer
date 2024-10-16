# -*- coding: utf-8 -*-
import json
import time
import requests
import datetime
import threading
import collections
from sds011 import SDS011

pm10, pm25 = 0.1, 0.1
usv_list = collections.deque(maxlen = 60)

def avg(arr):
    if len(arr) == 0:
        return 0
    average = sum(arr) / len(arr)
    return average

def sds011():
    global pm10, pm25
    sds = SDS011("/dev/ttyUSB0", use_query_mode = True)
    sds.sleep(sleep = False)
    while True:
        try:
            time.sleep(20)
            sds_data = sds.query()
            if sds_data[0] > 0:
               pm25 = sds_data[0]
            else:
               pm25 = 10.0
            if sds_data[1] > 0:
               pm10 = sds_data[1]
            else:
               pm10 = 10.0
            sds.sleep()
            time.sleep(40)
            sds.sleep(sleep = False)
        except Exception as e:
            print(f"{datetime.datetime.now().strftime('[%H:%M:%S]')} Error: {e}")
            time.sleep(1)
            continue

def main():
    while True:
        try:
            esp8266_data = requests.get("http://192.168.0.137", timeout = 5).json()
            usv_list.append(esp8266_data["usv"])
            data = {
                "temperature": esp8266_data["temperature"],
                "humidity": esp8266_data["humidity"],
                "pressure": esp8266_data["pressure"],
                "pm2.5": pm25,
                "pm10": pm10,
                "usv": esp8266_data["usv"],
                "usv_avg": avg(usv_list),
                "create_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            with open("/var/www/html/data.json", "w", encoding = "utf-8") as f:
                json.dump(data, f)
            time.sleep(60)
        except Exception as e:
            print(f"{datetime.datetime.now().strftime('[%H:%M:%S]')} Error: {e}")
            time.sleep(1)
            continue

thread1 = threading.Thread(target = sds011)
thread2 = threading.Thread(target = main)
thread1.start()
thread2.start()
