from ili9341 import Display, color565
from xpt2046 import Touch
from xglcd_font import XglcdFont
from machine import sleep, SoftI2C, Pin, SPI, time_pulse_us, idle
from utime import ticks_diff, ticks_us
import hrcalc
import time
from byul_funciones import ButtonDemo

def test():

    spi_display = SPI(1, baudrate=10000000, sck=Pin(26), mosi=Pin(27))
    display = Display(spi_display, dc=Pin(14), cs=Pin(13), rst=Pin(12))
    spi_touch = SPI(2, baudrate=1000000, sck=Pin(25), mosi=Pin(32), miso=Pin(35))
    touch = Touch(spi_touch, cs=Pin(33), int_pin=Pin(34))
    broadway_font = XglcdFont('fonts/Broadway17x15.c', 17, 15)


    demo = ButtonDemo(display, touch, broadway_font)
    try:
        demo.run()
    except KeyboardInterrupt:
        print("\nCtrl-C pressed. Cleaning up and exiting...")
    finally:
        display.cleanup()

test()         