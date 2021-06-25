#!/usr/bin/env python3
import test_rf
import time
import argparse
import socket


def main():
    parser = argparse.ArgumentParser(description="rf arguments")
    parser.add_argument("gateway_ip", help="ip address of gateway", type=str)
    parser.add_argument("gateway_port", help="port of gateway", type=str)
    parser.add_argument("rf_address", help="rf address", type=str)
    parser.add_argument("test_times", help="how many times to test", type=str)
    parser.add_argument("ping_operation", help="0 - read | 1 - online", type=str)

    gateway = parser.parse_args().gateway_ip
    port = int(parser.parse_args().gateway_port)
    rf_addr = parser.parse_args().rf_address
    sub = int(parser.parse_args().ping_operation)
    test = int(parser.parse_args().test_times)

    recv_count = 0
    timeout_count = 0
    error_count = 0
    test_rf.serverAddressPort = (gateway, port)
    test_rf.rf = rf_addr

    for x in range(test):
        test_rf.error_count = 0
        res = test_rf.ping(sub)
        if res[0] == "received":
            recv_count += 1
        if res[0] == "timeout":
            timeout_count += 1
        error_count += res[1]
    print("{} {} {}".format(recv_count, timeout_count, error_count), end="")


if __name__ == "__main__":
    main()
