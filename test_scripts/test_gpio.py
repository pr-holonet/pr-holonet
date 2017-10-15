"""
    simple script to read value from one GPIO pin
"""
import RPi.GPIO as GPIO

InputPin = 18

def do_gpio_setup():
    pass

def do_gpio_read(pin):
    # use BCM GPIO 00..nn numbers
    GPIO.setmode(GPIO.BCM)

    # set up the GPIO channels - one input and one output
    GPIO.setup(InputPin, GPIO.IN)
    value = GPIO.input(pin)
    return value


if __name__ == "__main__":
    value = do_gpio_read(InputPin)
    print("pin {} is: {}".format(InputPin, value))
