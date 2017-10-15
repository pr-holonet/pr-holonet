import RPi.GPIO as GPIO
import time
import os

#adjust for where your switch is connected
buttonPin = 18
sleep = 300
prev_input = 0
GPIO.setmode(GPIO.BCM)
GPIO.setup(buttonPin,GPIO.IN)

while True:
input = GPIO.input(buttonPin)
if ((not prev_input) and input):
    #os.system("curl something")
    os.system("date >> /tmp/test")
prev_input = input
time.sleep(sleep)
