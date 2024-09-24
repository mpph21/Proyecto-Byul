from time import sleep
from ili9341 import Display, color565
from machine import Pin, SPI, I2C
from xglcd_font import XglcdFont
from mlx90614 import MLX90614

# Configuración del display
spi_display = SPI(1, baudrate=10000000, sck=Pin(26), mosi=Pin(27))
display = Display(spi_display, dc=Pin(14), cs=Pin(13), rst=Pin(12))
broadway = XglcdFont('fonts/Broadway17x15.c', 17, 15)

# Configuración del sensor
i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=100000) 
sensor = MLX90614(i2c)  # Utiliza MLX90614 para el modelo que estás usando

# Función para mostrar la temperatura del objeto (persona)
def mostrar_temperatura_objeto():
    display.clear(color565(0, 255, 255))  # Limpiar pantalla con color cyan
    temp_objeto = sensor.object_temp      # Leer temperatura del objeto

    # Mostrar la temperatura del objeto en pantalla
    display.draw_text(10, 30, 'Temperatura Persona:', broadway, color565(0, 0, 0), color565(0, 255, 255))
    display.draw_text(10, 60, '{:.2f} C'.format(temp_objeto), broadway, color565(0, 0, 0), color565(0, 255, 255))

# Bucle para actualizar los valores de temperatura cada 2 segundos
try:
    while True:
        mostrar_temperatura_objeto()  # Mostrar la temperatura del objeto en pantalla
        sleep(2)                      # Esperar 2 segundos antes de actualizar
except KeyboardInterrupt:
    display.cleanup()                 # Limpiar la pantalla al detener el programa

