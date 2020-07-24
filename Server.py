import socket
import sys
import argparse 
import random
from datetime import datetime
import threading
import time
import RPi.GPIO as GPIO
import Adafruit_GPIO.SPI as SPI
import Adafruit_MCP3008
import graphs

################
# Pi Variables #
################
motor_pin = 8
light_pin = 10
soil_pin = 12

#Setup pi pins
GPIO.setmode(GPIO.BOARD)
GPIO.setup(motor_pin, GPIO.OUT, initial=GPIO.HIGH)
GPIO.setup(light_pin, GPIO.OUT, initial=GPIO.HIGH)
GPIO.setup(soil_pin, GPIO.OUT)
GPIO.setwarnings(False)

#Setup MCP3008
SPI_PORT   = 0
SPI_DEVICE = 0
mcp = Adafruit_MCP3008.MCP3008(spi=SPI.SpiDev(SPI_PORT, SPI_DEVICE))

###################
# Plant Variables #
###################
current_saturation = 0
last_update = datetime(1970, 1, 1)
last_watering = datetime(1970, 1, 1)
light_on = False

#################
# User Settings #
#################
log_time = 15 # minutes in between automatic saturation check and logging
auto_lights = False
turn_lights_on_time = "10:00:00"
turn_lights_off_time = "23:00:00"
auto_watering = False
lower_sat_bound = 50.0 #threshold for determining if the plant needs to be watered
water_when_light = True #only automatically water if the light is on
pump_on_time = 3 # seconds the pump is turned on for at a time


#code for handling the actual watering of the plant goes here
def water():
    #water the plant
    #Because of this relay, pulling the pin LOW turns the device ON
    GPIO.output(motor_pin, GPIO.LOW)
    time.sleep(pump_on_time)
    GPIO.output(motor_pin, GPIO.HIGH)

    #update records
    global last_watering 
    last_watering = datetime.now()
    add_record(True)


#Changes status of the grow light
# < 0: off
# = 0: toggle
# > 0: on
def change_light(action):
    global light_on
    if (action < 0 or (action == 0 and light_on)):
        light_on = False
        GPIO.output(light_pin, GPIO.HIGH)
        
    else:
        light_on = True
        GPIO.output(light_pin, GPIO.LOW)
    

#Handles updating the saturation level
def update_saturation():
    #read sensor and map it to a 0-100 scale
    #349 lower bound
    #733 upper bound
    global current_saturation
    current_saturation = round((1024 - mcp.read_adc_difference(0) - 349) * (100.0) / (733 - 349), 1)
    if (current_saturation < 0):
        current_saturation = 0.0
    elif (current_saturation > 100):
        current_saturation = 100.0

    #update timestamp
    global last_update 
    last_update = datetime.now()
    add_record()


#Takes an array of settings an updates vars and (optionally) csv
def update_settings(settings, update_file=True):
    #AutoLights, OnTime, OffTime, AutoWater, LowThresh, UpThresh, PumpTime
    global auto_lights, turn_lights_on_time, turn_lights_off_time, auto_watering, lower_sat_bound, water_when_light, pump_on_time
    auto_lights = settings[0].lower() == "true"
    turn_lights_on_time = settings[1]
    turn_lights_off_time = settings[2]
    auto_watering = settings[3].lower() == "true"
    if (0 <= int(settings[4]) <= 100):
        lower_sat_bound = int(settings[4])
    water_when_light = settings[5].lower() == "true"
    pump_on_time = int(settings[6]) if (0 < int(settings[6]) < 10) else pump_on_time

    if (update_file):
        f = open("settings.dat", 'w')
        f.write(str(auto_lights) + "," + str(turn_lights_on_time) + "," + str(turn_lights_off_time) + "," + str(auto_watering) + "," + str(lower_sat_bound) + "," + str(water_when_light) + "," + str(pump_on_time))
        f.close()


def send_settings_to_browser(sock):
    sock.send("HTTP/1.1 200 OK\r\n\r\n".encode('utf-8'))
    data = str(auto_lights) + "," + str(turn_lights_on_time) + "," + str(turn_lights_off_time) + "," + str(auto_watering) + "," + str(lower_sat_bound) + "," + str(water_when_light) + "," + str(pump_on_time)
    sock.send(data.encode('utf-8'))
    sock.send("\r\n".encode('utf-8'))
    
    
def load_settings_and_dates_from_file():
    try:
        f = open("settings.dat", 'r')
        settings = f.read().split(',')
        update_settings(settings, False)
        f.close()
    except:
        pass
        
        
    #TODO: make implementation not have to read every line
    try:
        f = open("data.csv", 'r')
        for entry in reversed(list(f)):
            entry = entry.split(',')
            if(entry[2].strip() == "True"):
                global last_watering
                last_watering = datetime.strptime(entry[0], '%d/%m/%Y %H:%M')
                break
                
        f.close()
    except:
        pass


#Appends current stats to data.csv
def add_record(is_watering=False):
    f = open("data.csv", "a")
    f.write("\n" + datetime.now().strftime("%d/%m/%Y %H:%M") + ", " + str(current_saturation) + ", " + str(is_watering) + ", " + str(light_on))
    f.close()


def send_data_to_browser(sock):
    sock.send("HTTP/1.1 200 OK\r\n\r\n".encode('utf-8'))
    data = str(current_saturation) + "," + str(light_on) + "," + last_update.strftime("%d %b %Y %H:%M") + "," + last_watering.strftime("%d %b %Y %H:%M")
    sock.send(data.encode('utf-8'))
    sock.send("\r\n".encode('utf-8'))


def send_file_to_browser(sock, filename):
    f = open(filename)
    outputdata = f.read()
    f.close()
    sock.send("HTTP/1.1 200 OK\r\n\r\n".encode('utf-8'))
    
    for i in range(len(outputdata)):  
        sock.send(outputdata[i].encode('utf-8'))
    sock.send("\r\n".encode('utf-8'))


def server_handler(server_socket):
    while True:
        connection_socket, addr = server_socket.accept()

        try:
            message = connection_socket.recv(1024)
            action = "empty" if len(message.split()) < 2 else message.split()[1]
            action = action.split('?')[0] #don't consider anything after a ? in a request

            if action == b'/water':
                water()
                send_data_to_browser(connection_socket)

            elif action == b'/updateLevel':
                update_saturation()
                send_data_to_browser(connection_socket)

            elif action == b'/currentLevel':
                send_data_to_browser(connection_socket)
                
            elif action == b'/light':
                change_light(0)
                send_data_to_browser(connection_socket)
                
            elif action == b'/save_settings':
                update_settings((message.split()[-1]).split(','))
                
            elif action == b'/load_settings':
                send_settings_to_browser(connection_socket)
                
            elif action == b'/logs':
                send_file_to_browser(connection_socket, 'data.csv')
                
            elif action == b'/graphs':
                send_file_to_browser(connection_socket, 'graphs.html')
                
            elif action == b'/satgraph.svg':
                send_file_to_browser(connection_socket, 'satgraph.svg')
                
            elif action == b'/request_graph':
                graphs.saturation_graph(message.split()[-1])
                connection_socket.send("HTTP/1.1 200 OK\r\n\r\n\r\n".encode('utf-8'))

            else:
                send_file_to_browser(connection_socket, 'index.html')

            connection_socket.close()

        except IOError:
            connection_socket.close()
    
    server_socket.close()  

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--host", action="store", dest="host", help="default 127.0.0.1")
    p.add_argument("--port", action="store", dest="port", type=int, help="default 12000")
    args = p.parse_args()
    host = args.host if args.host is not None else "127.0.0.1"
    port = args.port if args.port is not None else 12000
    
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((host, port))
    server_sock.listen(2)

    #Start threads
    server_thread = threading.Thread(target=server_handler, args=(server_sock,))
    server_thread.start()
    
    #load last saved settings and last water / refresh dates
    load_settings_and_dates_from_file()
    
    try:
        while True:
            
            #Update saturation every log_time minutes
            dif = datetime.now() - last_update
            if(dif.seconds // 60 >= log_time):
                update_saturation()
                
                #Water plant if saturation too low
                if(auto_watering and current_saturation < lower_sat_bound):
                    if (not water_when_light or light_on):
                        water()
                        update_saturation()
                    
            #Test for auto changing the lights
            if (auto_lights):
                current_time = datetime.strptime(datetime.now().strftime("%H:%M:%S"), '%H:%M:%S')
                target_off_time = datetime.strptime(turn_lights_off_time, '%H:%M:%S')
                target_on_time = datetime.strptime(turn_lights_on_time, '%H:%M:%S')

                if (-10 <= (target_off_time - current_time).total_seconds() <= 0):
                    change_light(-1) #Off
                elif (-10 <= (target_on_time - current_time).total_seconds() <= 0):
                    change_light(1) #On
            
            #busy wait
            time.sleep(0.5)

    except KeyboardInterrupt:
        #close all threads
        server_sock.close()
        server_thread.join()
        
        #Turn off all appliances
        GPIO.output(light_pin, GPIO.HIGH)
        GPIO.output(motor_pin, GPIO.HIGH)
        GPIO.cleanup()
        
        print("All threads successfully terminated")
