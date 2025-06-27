# -*- coding: utf-8 -*-
import json
import time
import struct
import serial
import datetime
import threading
import collections
from sds011 import SDS011

# === 全局参数 ===
ESP_PORT = "/dev/ttyUSB1"
ESP_BAUDRATE = 19200
SYNC_WORD = 0x8A
USV_WINDOW = 60  # 用于 usv 平均值的队列长度

SDS_PORT = "/dev/ttyUSB2"
SDS_QUERY_INTERVAL = 60  # 秒

OUTPUT_FILE = "/var/www/html/data.json"

# 全局状态
pm25 = 0.1
pm10 = 0.1
usv_list = collections.deque(maxlen=USV_WINDOW)


# === 辅助函数 ===
def calc_checksum(floats):
    """按 Arduino 代码的方式计算 checksum：所有 float 字节异或"""
    cs = 0
    for f in floats:
        b = struct.pack("<f", f)
        for byte in b:
            cs ^= byte
    return cs


def read_esp_packet(ser):
    """从 ESP8266 串口同步读取并解析一个数据包，返回 (temp, hum, pres, usv)"""
    # 找到 SYNC_WORD
    while True:
        b = ser.read(1)
        if not b:
            return None
        if b[0] == SYNC_WORD:
            break
    # 读取 4 floats + 1 checksum 共 17 字节
    payload = ser.read(4 * 4 + 1)
    if len(payload) != 17:
        return None
    data_bytes = payload[:-1]
    recv_cs = payload[-1]
    vals = struct.unpack("<4f", data_bytes)
    cs = calc_checksum(vals)
    if cs != recv_cs:
        print(
            f"[{datetime.datetime.now():%H:%M:%S}] ⚠️ 校验失败：计算 {cs:#02x} != 接收 {recv_cs:#02x}"
        )
        return None
    return vals  # (temperature, humidity, pressure, usv)


def avg(arr):
    return sum(arr) / len(arr) if arr else 0.0


# === SDS011 线程 ===
def sds011_worker():
    global pm25, pm10
    sds = SDS011(SDS_PORT, use_query_mode=True)
    sds.sleep(sleep=False)
    while True:
        try:
            time.sleep(20)
            data = sds.query()  # (pm2.5, pm10)
            pm25 = data[0] if data[0] > 0 else 10.0
            pm10 = data[1] if data[1] > 0 else 10.0
            sds.sleep()
            # wait until next interval
            time.sleep(SDS_QUERY_INTERVAL - 20)
            sds.sleep(sleep=False)
        except Exception as e:
            print(f"[{datetime.datetime.now():%H:%M:%S}] SDS011 Error: {e}")
            time.sleep(5)


# === 主逻辑 ===
def main():
    # 打开 ESP8266 串口
    try:
        ser = serial.Serial(ESP_PORT, ESP_BAUDRATE, timeout=1)
        print(f"✅ 打开串口 {ESP_PORT}，波特率 {ESP_BAUDRATE}")
    except Exception as e:
        print(f"❌ 无法打开串口 {ESP_PORT}: {e}")
        return

    # 丢弃遗留数据
    ser.reset_input_buffer()

    while True:
        # 读取 ESP8266 数据
        pkt = None
        for _ in range(10):  # 最多尝试 10 次
            pkt = read_esp_packet(ser)
            if pkt:
                break
        if not pkt:
            print(
                f"[{datetime.datetime.now():%H:%M:%S}] ⚠️ 未能读取到有效 ESP8266 数据包"
            )
            time.sleep(5)
            continue

        temperature, humidity, pressure, usv = pkt
        # 更新 usv 平均队列
        usv_list.append(usv)

        # 构造输出数据
        data = {
            "temperature": round(temperature, 2),
            "humidity": round(humidity, 2),
            "pressure": round(pressure, 2),
            "pm2.5": round(pm25, 1),
            "pm10": round(pm10, 1),
            "usv": round(usv, 4),
            "usv_avg": round(avg(usv_list), 4),
            "create_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        # 写入 JSON 文件
        try:
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[{data['create_at']}] 写入 {OUTPUT_FILE}")
        except Exception as e:
            print(f"[{datetime.datetime.now():%H:%M:%S}] 写文件 Error: {e}")

        # 等待下一个周期
        time.sleep(60)


if __name__ == "__main__":
    # 启动 SDS011 线程
    t = threading.Thread(target=sds011_worker, daemon=True)
    t.start()
    # 运行主循环
    main()
