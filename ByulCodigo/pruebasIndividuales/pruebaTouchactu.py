from ili9341 import Display, color565
from xpt2046 import Touch
from machine import idle, Pin, SPI  # type: ignore

class Demo(object):
    """Touchscreen simple demo."""
    CYAN = color565(0, 255, 255)
    PURPLE = color565(255, 0, 255)
    WHITE = color565(255, 255, 255)
    RED = color565(255, 0, 0)  # Color para los puntos

    def __init__(self, display, touch):
        """Initialize box.

        Args:
            display (ILI9341): display object
            touch (XPT2046): touch object
        """
        self.display = display
        self.touch = touch
        # Display initial message
        self.display.draw_text8x8(self.display.width // 2 - 32,
                                  self.display.height - 9,
                                  "TOUCH ME",
                                  self.WHITE,
                                  background=self.PURPLE)

        # A small 5x5 sprite for the dot
        self.dot = bytearray(b'\x00\x00\x07\xE0\xF8\x00\x07\xE0\x00\x00\x07\xE0\xF8\x00\xF8\x00\xF8\x00\x07\xE0\xF8\x00\xF8\x00\xF8\x00\xF8\x00\xF8\x00\x07\xE0\xF8\x00\xF8\x00\xF8\x00\x07\xE0\x00\x00\x07\xE0\xF8\x00\x07\xE0\x00\x00')

        # Set touch interrupt handler
        self.touch.int_handler = self.touch_interrupt

    def touch_interrupt(self, x, y):
        """Process touchscreen interrupt events."""
        if x is not None and y is not None:
            # Y needs to be flipped
            y = (self.display.height - 1) - y
            # Display coordinates
            self.display.draw_text8x8(self.display.width // 2 - 32,
                                      self.display.height - 9,
                                      "{0:03d}, {1:03d}".format(x, y),
                                      self.CYAN)
            # Draw dot
            self.display.draw_sprite(self.dot, x - 2, y - 2, 5, 5)

    def run(self):
        """Run the demo."""
        while True:
            idle()  # Esperar eventos de toque

def test():
    """Test code."""
    # Configura SPI para la pantalla (SPI1)
    spi_display = SPI(1, baudrate=10000000, sck=Pin(26), mosi=Pin(27))
    display = Display(spi_display, dc=Pin(14), cs=Pin(13), rst=Pin(12))
    spi_touch = SPI(2, baudrate=1000000, sck=Pin(25), mosi=Pin(32), miso=Pin(35))
    touch = Touch(spi_touch, cs=Pin(33), int_pin=Pin(34))

    demo = Demo(display, touch)
    try:
        demo.run()
    except KeyboardInterrupt:
        print("\nCtrl-C pressed. Cleaning up and exiting...")
    finally:
        display.cleanup()

test()
