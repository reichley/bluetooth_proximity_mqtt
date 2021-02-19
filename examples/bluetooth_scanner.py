#!/usr/bin/env python3
from bt_proximity import BluetoothRSSI
import datetime
import time
import threading
import sys
import os
import paho.mqtt.publish as publish
import paho.mqtt.client as mqtt
import socket
import yaml
import json

credentials = yaml.safe_load(open('./creds.yaml'))
dev1 = credentials['database']['dev1']
user = credentials['database']['mqtt_user']
passw = credentials['database']['mqtt_pass']
server = credentials['database']['mqtt_server']

# List of bluetooth addresses to scan
BT_ADDR_LIST = [dev1]
DAILY = False # Set to True to invoke callback only once per day per address
DEBUG = True  # Set to True to print out debug messages
THRESHOLD = (-10,10)
SLEEP = 30
devices = [
        {"name": "nick_bt", "mac": dev1, "state": "not_home"}
    ]
hostname = socket.gethostname()

# Provide name of the location where device is (this will form part of the state topic)
LOCATION = hostname

# The final state topic will therefore be: HomeAssistant/Presence/LOCATION/DEVICE_NAME

# Update the follow MQTT Settings for your system.
MQTT_USER = user              # MQTT Username
MQTT_PASS = passw     # MQTT Password
MQTT_CLIENT_ID = "bttracker_{}".format(hostname)    # MQTT Client Id
MQTT_HOST_IP = server      # MQTT HOST
MQTT_PORT = 1883                # MQTT PORT (DEFAULT 1883)

MQTT_AUTH = {
    'username': MQTT_USER,
    'password': MQTT_PASS
}


def presence_callback(stated, signal):
    # print("Dummy callback function invoked")
    for device in devices:
        mac = device['mac']
        if mac in BT_ADDR_LIST:
            # print(mac)
            device['state'] = stated
        try:
            publish.single("bt/presence/" + LOCATION,
                # payload=device['state'],
                payload=json.dumps({'id':device['name'], 'name':device['name'], 'state':device['state'], 'rssi':signal}),
                hostname=MQTT_HOST_IP,
                client_id=MQTT_CLIENT_ID,
                auth=MQTT_AUTH,
                port=MQTT_PORT,
                protocol=mqtt.MQTTv311)
        except:
            pass

def bluetooth_listen(
        addr, threshold, callback, sleep=1, daily=True, debug=False):
    """Scans for RSSI value of bluetooth address in a loop. When the value is
    within the threshold, calls the callback function.

    @param: addr: Bluetooth address
    @type: addr: str

    @param: threshold: Tuple of integer values (low, high), e.g. (-10, 10)
    @type: threshold: tuple

    @param: callback: Callback function to invoke when RSSI value is within
                      the threshold
    @type: callback: function

    @param: sleep: Number of seconds to wait between measuring RSSI
    @type: sleep: int

    @param: daily: Set to True to invoke callback only once per day
    @type: daily: bool

    @param: debug: Set to True to print out debug messages and does not 
                   actually sleep until tomorrow if `daily` is True.
    @type: debug: bool
    """
    b = BluetoothRSSI(addr=addr)
    while True:
        rssi = b.request_rssi()
        if debug:
            print("---")
            print("addr: {}, rssi: {}".format(addr, rssi))
        # Sleep and then skip to next iteration if device not found
        if rssi is None:
            callback('not_home', -99)
            time.sleep(sleep)
            continue
        # Trigger if RSSI value is within threshold
        int_rssi = int(''.join(map(str, b.request_rssi())))
        if threshold[0] < int(''.join(map(str, b.request_rssi()))) < threshold[1]:
            callback('home', int_rssi)
            if daily:
                # Calculate the time remaining until next day
                now = datetime.datetime.now()
                tomorrow = datetime.datetime(
                    now.year, now.month, now.day, 0, 0, 0, 0) + \
                    datetime.timedelta(days=1)
                until_tomorrow = (tomorrow - now).seconds
                if debug:
                    print("Seconds until tomorrow: {}".format(until_tomorrow))
                else:
                    time.sleep(until_tomorrow)
        else:
            callback('not_home', int_rssi)
        # Delay between iterations
        time.sleep(sleep)


def start_thread(addr, callback, threshold=THRESHOLD, sleep=SLEEP,
                 daily=DAILY, debug=DEBUG):
    """Helper function that creates and starts a thread to listen for the
    bluetooth address.

    @param: addr: Bluetooth address
    @type: addr: str

    @param: callback: Function to call when RSSI is within threshold
    @param: callback: function

    @param: threshold: Tuple of the high/low RSSI value to trigger callback
    @type: threshold: tuple of int

    @param: sleep: Time in seconds between RSSI scans
    @type: sleep: int or float

    @param: daily: Daily flag to pass to `bluetooth_listen` function
    @type: daily: bool

    @param: debug: Debug flag to pass to `bluetooth_listen` function
    @type: debug: bool

    @return: Python thread object
    @rtype: threading.Thread
    """
    thread = threading.Thread(
        target=bluetooth_listen,
        args=(),
        kwargs={
            'addr': addr,
            'threshold': threshold,
            'callback': callback,
            'sleep': sleep,
            'daily': daily,
            'debug': debug
        }
    )
    # Daemonize
    thread.daemon = True
    # Start the thread
    thread.start()
    return thread


def main():
    if not BT_ADDR_LIST:
        print("Please edit this file and set BT_ADDR_LIST variable")
        sys.exit(1)
    threads = []
    for addr in BT_ADDR_LIST:
        th = start_thread(addr=addr, callback=presence_callback)
        threads.append(th)
    while True:
        # Keep main thread alive
        time.sleep(1)


if __name__ == '__main__':
    main()
