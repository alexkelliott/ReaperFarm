import socket
import sys    
import random
from datetime import datetime
import threading
import time
import RPi.GPIO as GPIO
import Adafruit_GPIO.SPI as SPI
import Adafruit_MCP3008
import graphs

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind(('10.0.0.6', 12000))
server_socket.listen(2)

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


###################
# User parameters #
###################
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
    auto_lights = settings[0] == "true"
    turn_lights_on_time = settings[1]
    turn_lights_off_time = settings[2]
    auto_watering = settings[3] == "true"
    if (0 <= int(settings[4]) <= 100):
        lower_sat_bound = int(settings[4])
    water_when_light = settings[5] == "true"
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
    
    
def load_settings_from_file():
    f = open("settings.dat", 'r')
    settings = f.read().split(',')
    f.close()
    update_settings(settings, False)


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
    
    for i in range(0, len(outputdata)):  
        sock.send(outputdata[i].encode('utf-8'))
    sock.send("\r\n".encode('utf-8'))


def server_handler():
    while True:
        connectionSocket, addr = server_socket.accept()

        try:
            message = connectionSocket.recv(1024)
            action = "empty" if len(message.split()) < 2 else message.split()[1]

            if action == b'/water':
                water()
                send_data_to_browser(connectionSocket)

            elif action == b'/updateLevel':
                update_saturation()
                send_data_to_browser(connectionSocket)

            elif action == b'/currentLevel':
                send_data_to_browser(connectionSocket)
                
            elif action == b'/light':
                change_light(0)
                send_data_to_browser(connectionSocket)
                
            elif action == b'/save_settings':
                update_settings((message.split()[-1]).split(','))
                
            elif action == b'/load_settings':
                send_settings_to_browser(connectionSocket)
                
            elif action == b'/logs':
                send_file_to_browser(connectionSocket, 'data.csv')
                
            elif action == b'/graphs':
                send_file_to_browser(connectionSocket, 'graphs.html')
                
            elif action == b'/satgraph.svg':
                send_file_to_browser(connectionSocket, 'satgraph.svg')
                
            elif action == b'/request_graph':
                print("/request_graph received")
                graphs.saturation_graph()
                send_file_to_browser(connectionSocket, 'satgraph.svg')

            else:
                send_file_to_browser(connectionSocket, 'index.html')

        		
            connectionSocket.close()

        except IOError:
            connectionSocket.close()
    
    server_socket.close()  

if __name__ == "__main__": 
    #Start threads
    server_thread = threading.Thread(target=server_handler, args=())
    server_thread.start()
    
    #load last saved settings
    load_settings_from_file()
    
    try:
        update_saturation()
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
        server_socket.close()
        server_thread.join()
        
        #Turn off all appliances
        GPIO.output(light_pin, GPIO.HIGH)
        GPIO.output(motor_pin, GPIO.HIGH)
        GPIO.cleanup()
        
        print("All threads successfully terminated")