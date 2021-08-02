#!/usr/bin/env python3
import time
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
import socket
import crcelk
from threading import Thread
from bitstring import BitArray

global flag_timeout, waiting_udp, current_position
current_position = 0

UDPClientSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
UDPClientSocket.settimeout(3)
serverAddressPort = ("10.0.100.131", 8080)
rf = "123477"
moving_pre_arrive_count = 1000
error_count = 0
config_reply = bytearray(b"")

bufferSize = 1024
sequence = b"\x00\x00"  # always acceptable
crc = crcelk.CrcAlgorithm(
    32, 0x04C11DB7, 'CRC-32/MPEG-2', 0xFFFFFFFF, False, False, 0)


def setup_logger(name, log_file, level=logging.INFO):
    handler = RotatingFileHandler(log_file, maxBytes=1e8, backupCount=10)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    if logger.hasHandlers():
        logger.handlers.clear()
    logger.addHandler(handler)
    return logger


udp_logger = setup_logger("rf_udp", "rf_udp.log")


# log with timestamp
def log_with_time(logger_name, string):
    logger_name.info("{} {}".format(datetime.now(timezone.utc).astimezone().isoformat(), string))
    return


# format the row recv data
def form(message):
    print_format = "seq: {} | rf: {}".format(
        message[0:2].hex(), message[2:5].hex())
    if message[5] == 0x00:  # ping message
        print_format += " | cmd: {} | protocol version: {}".format(
            message[5:6].hex(), message[6:7].hex())
        print_format += " | state: {} | CRC: {}".format(
            message[7:8].hex(), message[8:12].hex())
    elif message[5] == 0x01:  # homing message
        print_format += " | cmd: {} | homing state: {} | homing pos: {}".format(
            message[5:6].hex(), message[6:7].hex(), message[7:11].hex())
        print_format += " | abs pos: {} | CRC: {}".format(
            message[7:11].hex(), message[11:15].hex())
    elif message[5] in [0x02, 0x0A]:  # moving & moving_read message
        print_format += " | cmd: {} | pos: {} | velocity: {}".format(
            message[5:6].hex(), message[6:10].hex(), message[10:14].hex()
        )
        print_format += " | torque: {} | CRC: {}".format(
            message[14:16].hex(), message[16:20].hex())
    elif message[5] == 0x03:  # sort action message
        print_format += " | cmd: {} | action state: {}".format(
            message[5:6].hex(), message[6:7].hex())
        print_format += " | CRC: {}".format(message[7:11].hex())
    elif message[5] == 0x04:  # moving cancel
        print_format += " | cmd: {} | pos: {}".format(
            message[5:6].hex(), message[6:10].hex())
        print_format += " | CRC: {}".format(message[10:14].hex())
    elif message[5] == 0x76:  # halt action message
        print_format += " | cmd: {} | halt state: {}".format(
            message[5:6].hex(), message[6:7].hex())
        print_format += " | CRC: {}".format(message[7:11].hex())
    elif message[5] == (0x05 or 0xDD):  # sensor state or debug message
        sensor_state = BitArray(hex=message[6:7].hex())
        print_format += " | cmd: {}".format(message[5:6].hex())
        print_format += " | left sensor: {}".format(sensor_state.bin[7])
        print_format += " | centor sensor: {}".format(sensor_state.bin[6])
        print_format += " | right sensor: {}".format(sensor_state.bin[5])
        print_format += " | homing sensor: {}".format(sensor_state.bin[4])
        print_format += " | avoidance sensor: {}".format(sensor_state.bin[3])
        print_format += " | CRC: {}".format(message[7:11].hex())
    elif message[5] == 0xC0:  # configure message
        print_format += " | cmd: {} | r/w: {} | index: {}".format(
            message[5:6].hex(), message[6:7].hex(), message[7:9].hex()
        )
        print_format += " | sub-index: {} | data: {} | CRC: {}".format(
            message[9:10].hex(), message[10:14].hex(), message[14:18].hex()
        )
    else:  # unknown cmd
        print_format += "unknown recv cmd: {}".format(
            message[5:6].hex())
    return print_format


# UDP thread send
def send(message_send, message_type):
    while waiting_udp:
        log_with_time(udp_logger, "UDP sent: {}".format(message_send.hex()))
        UDPClientSocket.sendto(message_send, serverAddressPort)
        time.sleep(0.1)
        if message_type == "loading" or message_type == "unloading":
            data = bytearray(b"\x03")
            data += (0).to_bytes(1, byteorder="little")
            message_send = encode(data)
    else:
        return


def recv_and_log(msgReceive):
    try:
        msgReceive = UDPClientSocket.recv(bufferSize)
        log_with_time(udp_logger, "UDP recv: {}".format(form(msgReceive)))
    except Exception:
        pass
    return msgReceive


def log_error(information):
    global error_count
    error_count += 1
    log_with_time(udp_logger, "error: {}".format(information))


def log_timeout(information):
    global flag_timeout
    flag_timeout = True
    log_with_time(udp_logger, "timeout: {}".format(information))


# UDP thread recv
def recv(message_send, message_type):
    global waiting_udp
    global current_position
    # start different receiving modes according to message type
    # global variable: message_send, message_type
    msgReceive = recv_and_log(
        bytearray(b"\x77\x77\x77\x77\x77\x77\x77\x77\x77\x77\x77\x77\x77\x77"))
    msgReceive = recv_and_log(msgReceive)  # get reply of first send
    # normal command which only require 1 response
    if message_type == "general":
        pass
    elif message_type == "ping_read":
        timeout = time.time() + 3
        while msgReceive[5] != 0x00:
            if time.time() > timeout:
                log_timeout("ping read")
                break
            msgReceive = recv_and_log(msgReceive)
        if msgReceive[7] != 0x01 and msgReceive[7] != 0x02:
            log_error("ping state {}".format(msgReceive[7:8].hex()))
    elif message_type == "ping_online":
        timeout = time.time() + 3
        while not (msgReceive[5] == 0x00 and msgReceive[7] == 0x02):
            if time.time() > timeout:
                log_timeout("ping online")
                break
            msgReceive = recv_and_log(msgReceive)
    elif message_type == "homing_start":
        timeout = time.time() + 30
        while not (msgReceive[5] == 0x01 and msgReceive[6] == 0x03):
            if time.time() > timeout:
                log_timeout("too much time on homing")
                log_error("homing state {}".format(msgReceive[6:7].hex()))
                break
            msgReceive = recv_and_log(msgReceive)
        current_position = int.from_bytes(
            msgReceive[7:11], byteorder="little", signed=True)       
    elif message_type == "homing_reset":
        timeout = time.time() + 3
        while not (msgReceive[5] == 0x01 and msgReceive[6] == 0x00):
            if time.time() > timeout:
                log_timeout("too much time on homing reset")
                log_error("homing state {}".format(msgReceive[6:7].hex()))
                break
            msgReceive = recv_and_log(msgReceive)
        current_position = int.from_bytes(
            msgReceive[7:11], byteorder="little", signed=True)
    elif message_type == "moving":
        timeout = time.time() + 30
        while not msgReceive[5] == 0x02:
            if time.time() > timeout:
                log_timeout("cannot start moving")
                break
            msgReceive = recv_and_log(msgReceive)
        while abs(
            int.from_bytes(msgReceive[6: 10],
                           byteorder="little", signed=True) - int.from_bytes(
                message_send[6: 10],
                byteorder="little", signed=True)) > moving_pre_arrive_count:
            if time.time() > timeout:
                log_timeout("too much time on moving")
                break
            msgReceive = recv_and_log(msgReceive)
    elif message_type == "moving_with_sensor":
        timeout = time.time() + 30
        while not msgReceive[5] == 0x02:
            if time.time() > timeout:
                log_timeout("cannot start moving")
                break
            msgReceive = recv_and_log(msgReceive)
        while abs(
            int.from_bytes(msgReceive[6:10],
                           byteorder="little", signed=True) - int.from_bytes(
                message_send[6:10],
                byteorder="little", signed=True)) > moving_pre_arrive_count and 0 == msgReceive[16] & 0x01:
            if time.time() > timeout:
                log_timeout("too much time on moving")
                break
            msgReceive = recv_and_log(msgReceive)
    elif message_type == "moving_cancel":
        timeout = time.time() + 3
        while msgReceive[5] != 0x04:
            if time.time() > timeout:
                log_timeout("moving cancel")
                break
            msgReceive = recv_and_log(msgReceive)
    elif message_type == "action_read":
        if msgReceive[6] > 0x08:
            log_error("state {}".format(msgReceive[6:7].hex()))
    elif message_type == "loading":
        timeout = time.time() + 10
        while not (msgReceive[5] == 0x03 and msgReceive[6] == 0x03):
            if time.time() > timeout:
                log_timeout("cannot start loading")
                break
            msgReceive = recv_and_log(msgReceive)
        while msgReceive[6] == 0x03:
            if time.time() > timeout:
                log_timeout("too much time on loading")
                break
            msgReceive = recv_and_log(msgReceive)
        if msgReceive[6] != 0x04:
            log_error("action state {}".format(msgReceive[6:7].hex()))
    elif message_type == "unloading":
        timeout = time.time() + 10
        while not (msgReceive[5] == 0x03 and msgReceive[6] == 0x07):
            if time.time() > timeout:
                log_timeout("cannot start unloading")
                break
            msgReceive = recv_and_log(msgReceive)
        while msgReceive[6] == 0x07:
            if time.time() > timeout:
                log_timeout("too much time on unloading")
                break
            msgReceive = recv_and_log(msgReceive)
        if msgReceive[6] != 0x08:
            log_error("action state {}".format(msgReceive[6:7].hex()))
    elif message_type == "halt":
        timeout = time.time() + 5
        while not (msgReceive[5] == 0x76 and msgReceive[6] == 0x01):
            if time.time() > timeout:
                log_timeout("too much time on halting")
                if msgReceive[6] != 0x01:
                    log_error("halting state {}".format(msgReceive[6:7].hex()))
                break
            msgReceive = recv_and_log(msgReceive)
    elif message_type == "resume":
        timeout = time.time() + 5
        while not (msgReceive[5] == 0x76 and msgReceive[6] == 0x02):
            if time.time() > timeout:
                log_timeout("too much time on halting")
                if msgReceive[6] != 0x02:
                    log_error("halting state {}".format(msgReceive[6:7].hex()))
                break
            msgReceive = recv_and_log(msgReceive)
    elif message_type == "debug":
        while True:
            msgReceive = recv_and_log(msgReceive)
    elif message_type == "sensor_state":
        while True:
            msgReceive = recv_and_log(msgReceive)
    elif message_type == "moving_read":
        timeout = time.time() + 3
        while msgReceive[5] != 0x0A:
            if time.time() > timeout:
                log_timeout("moving read")
                break
            msgReceive = recv_and_log(msgReceive)
        current_position = int.from_bytes(msgReceive[6:10], byteorder="little", signed=True)
    elif message_type == "config":
        if message_send[6] == 0x40 and msgReceive[6] != 0x43:
            log_error("config write state {}".format(msgReceive[6:7].hex()))
        if message_send[6] == 0x23 and msgReceive[6] != 0x60:
            log_error("config read state {}".format(msgReceive[6:7].hex()))
    elif message_type == "reboot":
        pass
    waiting_udp = False
    return


# form a message with given data
def encode(data):
    message = bytearray(sequence)
    message += bytearray.fromhex(rf)
    message += data
    message += crc.calc_bytes(data).to_bytes(4, byteorder="big")
    return message


# test given message
def test(message, mess_type):
    global flag_timeout, waiting_udp
    flag_timeout = False
    waiting_udp = True
    # define threads
    trecv = Thread(target=recv, args=(message, mess_type))
    tsend = Thread(target=send, args=(message, mess_type))
    trecv.start()
    tsend.start()
    while trecv.is_alive() or tsend.is_alive():
        time.sleep(0.05)
        pass
    if flag_timeout:
        return ["timeout", error_count, current_position]
    return ["received", error_count, current_position]


# test ping 0x00
def ping(sub):
    mess_type = "ping_read" if sub == 0 else "ping_online"
    log_with_time(udp_logger, "test {}".format(mess_type))
    data = bytearray(b"\x00")
    data += sub.to_bytes(1, byteorder="little")
    return test(encode(data), mess_type)


# test homing 0x01
def homing(sub):
    mess_type = "homing_reset" if sub == 1 else "homing_start"
    log_with_time(udp_logger, "test {}".format(mess_type))
    data = bytearray(b"\x01")
    data += sub.to_bytes(1, byteorder="little")
    return test(encode(data), mess_type)


# test moving 0x02
def moving(pos, vel, is_dest, is_vert, is_sensor):
    mess_type = "moving" if is_sensor == 0 else "moving_with_sensor"
    log_with_time(udp_logger, "test {}".format(mess_type))
    data = bytearray(b"\x02")
    data += bytearray.fromhex(pos)  # "ffffffff"
    data += vel.to_bytes(4, byteorder="little")
    addi = 2 * is_dest
    addi += is_vert
    data += addi.to_bytes(1, byteorder="little")
    return test(encode(data), mess_type)


# test sort action 0x03
def sort_action(sub):
    mess_type = "action_read" if sub == 0 else "loading" if sub == 1 or sub == 2 else "unloading"
    log_with_time(udp_logger, "test {}".format(mess_type))
    data = bytearray(b"\x03")
    data += sub.to_bytes(1, byteorder="little")
    return test(encode(data), mess_type)


# test moving cancel 0x04
def moving_cancel():
    mess_type = "moving_cancel"
    log_with_time(udp_logger, "test {}".format(mess_type))
    data = bytearray(b"\x04")
    return test(encode(data), mess_type)


# sensor state 0x05
def sensor_state():
    mess_type = "sensor_state"
    log_with_time(udp_logger, "test {}".format(mess_type))
    data = bytearray(b"\x05")
    return test(encode(data), mess_type)


# test moving_read 0x0A
def moving_read():
    mess_type = "moving_read"
    log_with_time(udp_logger, "test {}".format(mess_type))
    data = bytearray(b"\x0A")
    return test(encode(data), mess_type)


# test halt action 0x76
def halt_action(sub):
    mess_type = "resume" if sub == 0 else "halt"
    log_with_time(udp_logger, "test {}".format(mess_type))
    data = bytearray(b"\x76")
    data += sub.to_bytes(1, byteorder="little")
    return test(encode(data), mess_type)


# test debug 0xdd
def debug(sub):
    # 0xD0 + sub-command
    sub += 208
    mess_type = "debug"
    data = bytearray(b"\xdd")
    data += sub.to_bytes(1, byteorder="little")
    return test(encode(data), mess_type)


# test configuration
def config(message):
    mess_type = "config"
    log_with_time(udp_logger, "test {}".format(mess_type))
    data = bytearray(b"\xc0")
    data += message
    return test(encode(data), mess_type)


# reboot
def reboot(message):
    mess_type = "reboot"
    test(encode(message), mess_type)
