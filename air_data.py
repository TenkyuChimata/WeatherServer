# -*- coding: utf-8 -*-
import json
import time
import struct
import serial
import datetime
import collections

# 同步字节
SYNC_WORD = 0x8A
# 3 个 float（4 字节 * 3） + 1 字节校验
PACKET_SIZE = struct.calcsize("<fffB")
usv_list = collections.deque(maxlen=60)


def avg(arr):
    if len(arr) == 0:
        return 0
    average = sum(arr) / len(arr)
    return average


def calculate_checksum(data_bytes):
    """对一段 bytes 做异或校验"""
    cs = 0
    for b in data_bytes:
        cs ^= b
    return cs


def read_sensor_packet(ser):
    """从串口不断读，找到 SYNC_WORD 后读取一个完整数据包并解析"""
    # 等待同步字节
    while True:
        byte = ser.read(1)
        if not byte:
            return None  # 可能超时
        if byte[0] == SYNC_WORD:
            break

    # 读出后面的数据包
    packet = ser.read(PACKET_SIZE)
    if len(packet) != PACKET_SIZE:
        return None

    float_bytes = packet[:12]  # 前 12 字节是三个 float
    recv_checksum = packet[12]  # 最后一字节是校验

    # 计算校验
    if calculate_checksum(float_bytes) != recv_checksum:
        print(
            f"{datetime.datetime.now().strftime('[%H:%M:%S]')} 校验失败，丢弃本次数据"
        )
        return None

    # 解包
    temperature, humidity, usv = struct.unpack("<fff", float_bytes)
    return {"temperature": temperature, "humidity": humidity, "usv": usv}


def main():
    # 请根据实际情况修改串口名称
    serial_port = "/dev/ttyUSB2"
    baudrate = 19200

    print(f"打开串口 {serial_port}，波特率 {baudrate} …")
    ser = serial.Serial(port=serial_port, baudrate=baudrate, timeout=5)
    time.sleep(2)  # 等待串口稳定

    try:
        while True:
            sensor = read_sensor_packet(ser)
            if sensor:
                usv_list.append(sensor["usv"])
                # 拼装要写入的 JSON
                data = {
                    "temperature": sensor["temperature"],
                    "humidity": sensor["humidity"],
                    "pm2.5": 0.0,
                    "pm10": 0.0,
                    "usv": sensor["usv"],
                    "usv_avg": avg(usv_list),
                    "create_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                # 写入文件（覆盖旧数据）
                with open("/var/www/html/data_seis.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
                print(
                    f"{datetime.datetime.now().strftime('[%H:%M:%S]')} 写入数据: {data}"
                )
                # 每次成功写入后等待 60 秒
                time.sleep(60)
            else:
                # 没读到或校验失败，短暂等待后重试
                time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n退出程序喵～")
    except Exception as e:
        print(f"{datetime.datetime.now().strftime('[%H:%M:%S]')} 未知错误: {e}")
    finally:
        ser.close()


if __name__ == "__main__":
    main()
