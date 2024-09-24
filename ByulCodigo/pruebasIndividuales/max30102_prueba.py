from max30102 import MAX30102, MAX30105_PULSE_AMP_MEDIUM
from machine import sleep, SoftI2C, Pin, Timer, SPI
from utime import ticks_diff, ticks_us
import hrcalc
from ili9341 import Display, color565
from xglcd_font import XglcdFont

# Configuración del display
spi_display = SPI(1, baudrate=10000000, sck=Pin(18), mosi=Pin(23))
display = Display(spi_display, dc=Pin(4), cs=Pin(15), rst=Pin(17))
broadway = XglcdFont('fonts/Broadway17x15.c', 17, 15)

# Configuración del LED
led = Pin(2, Pin.OUT)

# Configuración del sensor
i2c = SoftI2C(sda=Pin(21), scl=Pin(22), freq=400000)
sensor = MAX30102(i2c=i2c)

# Verificar conexión del sensor
if sensor.i2c_address not in i2c.scan():
    print("Sensor no encontrado.")
elif not sensor.check_part_id():
    print("ID de dispositivo I2C no corresponde a MAX30102 o MAX30105.")
else:
    print("Sensor conectado y reconocido.")

# Configuración del sensor
print("Configurando el sensor con configuración predeterminada.")
sensor.setup_sensor()
sensor.set_sample_rate(400)
sensor.set_fifo_average(16)  # Aumentar el promedio para una lectura más estable
sensor.set_active_leds_amplitude(MAX30105_PULSE_AMP_MEDIUM)
sensor.set_led_mode(2)
sleep(1)

# Inicialización de variables para BPM
MAX_HISTORY = 64  # Aumentar el tamaño del historial
history = []
beats_history = []
beat = False
beats = 0
counter = 0
limit = 150

# Buffers para almacenamiento de datos
red_buf = []
ir_buf = []

# Tiempo de inicio
t_start = ticks_us()

# Umbral para detectar si no hay dedo en el sensor
NO_FINGER_THRESHOLD = 100  # Ajusta este valor según sea necesario

def smooth_bpm(beats_history, window_size=5):
    """ Suavizar el valor BPM utilizando un promedio móvil """
    if len(beats_history) == 0:
        return 0
    if len(beats_history) < window_size:
        return beats_history[-1]
    return sum(beats_history[-window_size:]) / window_size

def filter_extreme_values(data, threshold=20):
    """ Filtrar valores extremos basados en un umbral """
    if len(data) == 0:
        return data
    mean = sum(data) / len(data)
    return [x for x in data if abs(x - mean) < threshold]

def calculate_bpm(t_start, value, beat, threshold_on, threshold_off):
    """ Calcular BPM basado en los valores del sensor """
    if value > 1000:
        if not beat and value > threshold_on:
            beat = True
            t_us = ticks_diff(ticks_us(), t_start)
            t_s = t_us / 1000000
            bpm = (1 / t_s) * 60
            if bpm < 300:  # Ajustar el filtro para valores absurdos
                t_start = ticks_us()
                return round(bpm, 2), t_start, beat
        if beat and value < threshold_off:
            beat = False
    return None, t_start, beat

def display_data(bpm, spo2):
    """ Mostrar BPM y SpO2 en pantalla """
    display.clear(color565(0, 255, 255))  # Limpiar la pantalla con color cyan
    
    # Mostrar la frecuencia cardíaca (BPM)
    display.draw_text(10, 30, 'Frecuencia Cardiaca:', broadway, color565(0, 0, 0), color565(0, 255, 255))
    
    if isinstance(bpm, (int, float)):  # Verificar si BPM es un número
        display.draw_text(10, 60, '{:.2f} BPM'.format(bpm), broadway, color565(0, 0, 0), color565(0, 255, 255))
    else:
        display.draw_text(10, 60, '{} BPM'.format(bpm), broadway, color565(0, 0, 0), color565(0, 255, 255))
    
    # Mostrar la saturación de oxígeno (SpO2)
    display.draw_text(10, 90, 'Saturacion Oxigeno:', broadway, color565(0, 0, 0), color565(0, 255, 255))
    
    if isinstance(spo2, (int, float)):  # Verificar si SpO2 es un número
        display.draw_text(10, 120, '{:.2f} %'.format(spo2), broadway, color565(0, 0, 0), color565(0, 255, 255))
    else:
        display.draw_text(10, 120, '{} %'.format(spo2), broadway, color565(0, 0, 0), color565(0, 255, 255))

def display_no_finger():
    """ Mostrar mensaje de 'No finger detected' en pantalla """
    display.clear(color565(255, 0, 0))  # Limpiar la pantalla con color rojo
    display.draw_text(10, 60, 'No finger detected', broadway, color565(255, 255, 255), color565(255, 0, 0))

# Bucle principal de lectura de datos
while True:
    try:
        sensor.check()
        if sensor.available():
            red_reading = sensor.pop_red_from_storage()
            ir_reading = sensor.pop_ir_from_storage()
            
            if red_reading < NO_FINGER_THRESHOLD:
                print("No finger detected.")
                display_no_finger()  # Mostrar mensaje en pantalla
                continue

            value = red_reading
            history.append(value)
            history = history[-MAX_HISTORY:]
            
            minima, maxima = min(history), max(history)
            threshold_on = (minima + maxima * 3) // 4
            threshold_off = (minima + maxima) // 2
            
            bpm, t_start, beat = calculate_bpm(t_start, value, beat, threshold_on, threshold_off)
            if bpm:
                beats_history.append(bpm)
                beats_history = filter_extreme_values(beats_history)
            
            if counter == limit:
                # Obtener resultado del cálculo
                result = hrcalc.calc_hr_and_spo2(ir_buf, red_buf)
                hr = result[0] if result[1] else 'Error'
                spo2 = result[2] if result[3] else 'Error'
                
                # Mostrar BPM y SpO2 en pantalla
                display_data(hr, spo2)
                
                # Reiniciar el contador y los buffers
                counter = 0
                red_buf = []
                ir_buf = []
            else:
                red_buf.append(red_reading)
                ir_buf.append(ir_reading)
                counter += 1
                
        # Introducir un retraso de 1 segundo entre cada lectura del sensor
        sleep(1)
                
    except Exception as e:
        print("Error:", e)
        led.off()
        sleep(1)  # Esperar antes de intentar de nuevo
