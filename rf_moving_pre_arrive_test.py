#!/usr/bin/env python3
import test_rf
import time
import argparse
import socket


def main():
    parser = argparse.ArgumentParser(description="rf arguments")
    parser.add_argument("gateway_ip", help="ip address of gateway", type=str)
    parser.add_argument("gateway_port", help="port of gateway", type=int)
    parser.add_argument("rf_address", help="rf address", type=str)
    parser.add_argument("test_times", help="how many times to test", type=int)
    parser.add_argument("target_pos", help="absolute target in counts in hex", type=str)
    parser.add_argument("velocity", help="velocity in counts/s", type=int)
    parser.add_argument("is_destination", help="0 - not | 1 - is dest", type=int)
    parser.add_argument("is_vertical", help="0 - horizontal | 1 - vertical", type=int)
    parser.add_argument("pre_arrive_count", help="pre arrive distance in counts", type=int)
    parser.add_argument("is_sensor_triggered", help="0 - no sensor | 1 - has sensor", type=int)

    gateway = parser.parse_args().gateway_ip
    port = parser.parse_args().gateway_port
    rf_addr = parser.parse_args().rf_address
    test = parser.parse_args().test_times
    pos = parser.parse_args().target_pos
    vel = parser.parse_args().velocity
    is_dest = parser.parse_args().is_destination
    is_vert = parser.parse_args().is_vertical
    pre_arrive = parser.parse_args().pre_arrive_count
    is_sensor = parser.parse_args().is_sensor_triggered

    recv_count = 0
    timeout_count = 0
    error_count = 0
    test_rf.serverAddressPort = (gateway, port)
    test_rf.rf = rf_addr
    test_rf.moving_pre_arrive_count = pre_arrive

    for x in range(test):
        test_rf.error_count = 0
        res = test_rf.moving(pos, vel, is_dest, is_vert, is_sensor)
        if res[0] == "received":
            recv_count += 1
        if res[0] == "timeout":
            timeout_count += 1
        error_count += res[1]
    print("{} {} {}".format(recv_count, timeout_count, error_count), end="")


if __name__ == "__main__":
    main()
