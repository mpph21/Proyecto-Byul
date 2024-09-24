from ili9341 import Display, color565
from xpt2046 import Touch
from xglcd_font import XglcdFont
from max30102 import MAX30102, MAX30105_PULSE_AMP_MEDIUM
from machine import sleep, SoftI2C, Pin, SPI, time_pulse_us, idle
from utime import ticks_diff, ticks_us
import hrcalc
from mlx90614 import MLX90614
import time
from auxInfo import exploration_steps, burn_steps, steps,  choking_steps, rcp_steps, emergency_steps, hemorrhage_steps

class ButtonDemo(object):
    """Touchscreen button demo with multiple screens and custom font."""
    CYAN = color565(0, 255, 255)
    BLUE = color565(0, 0, 255)  # Fondo azul
    BLACK = color565(0, 0, 0)   # Texto negro
    LIGHT_BLUE = color565(173, 216, 230)  # Fondo celeste para los botones
    MAX_WIDTH = 220
    CHAR_WIDTH = 10

    def __init__(self, display, touch, font):
        """Initialize demo with buttons and custom font."""
        self.display = display
        self.touch = touch
        self.font = font
        self.main_menu = True  # Flag to know if we're in the main menu
        self.in_information_menu = False  # Track if in Information submenu
        self.current_step = 0  # Track the current step of the information
        self.current_page = 0
        
    
        self.draw_buttons()
        # Set touch interrupt handler
        self.touch.int_handler = self.touch_interrupt
        self.in_option_screen = False
        self.current_info_type = None
        self.sensors_initialized = False
        self.trigger = Pin(18, Pin.OUT)
        self.echo = Pin(19, Pin.IN)
        
        # Inicializamos la última distancia medida
        self.ultima_distancia = 500  # Inicializamos con un valor grande
        self.ultima_medicion_tiempo = time.time()
        
        
    def init_sensors(self):
        # Configuración de pines para el sensor de distancia
        self.trigger = Pin(18, Pin.OUT)
        self.echo = Pin(19, Pin.IN)
        
        # Configuración del sensor MAX30102
        i2c = SoftI2C(sda=Pin(21), scl=Pin(22), freq=100000)
        self.sensor_max = MAX30102(i2c=i2c)
        
        # Configuración del sensor MLX90614
        self.sensor_temp = MLX90614(i2c)
        
        # Verificar conexión del sensor MAX30102
        if self.sensor_max.i2c_address not in i2c.scan():
            print("Sensor MAX30102 no encontrado.")
        elif not self.sensor_max.check_part_id():
            print("ID de dispositivo I2C no corresponde a MAX30102 o MAX30105.")
        else:
            print("Sensor MAX30102 conectado y reconocido.")
        
        # Configuración del sensor MAX30102
        self.sensor_max.setup_sensor()
        self.sensor_max.set_sample_rate(400)
        self.sensor_max.set_fifo_average(16)
        self.sensor_max.set_active_leds_amplitude(MAX30105_PULSE_AMP_MEDIUM)
        self.sensor_max.set_led_mode(2)
        
        # Inicialización de variables para MAX30102
        self.MAX_HISTORY = 64
        self.history = []
        self.beats_history = []
        self.beat = False
        self.beats = 0
        self.counter = 0
        self.limit = 150
        self.temp_counter = 0
        
        # Buffers para almacenamiento de datos del MAX30102
        self.red_buf = []
        self.ir_buf = []
        
        # Tiempo de inicio
        self.t_start = time.ticks_us()
        
        # Umbral para detectar si no hay dedo en el sensor
        self.NO_FINGER_THRESHOLD = 100
        
        # Intervalo de medición de distancia
        self.DISTANCE_CHECK_INTERVAL = 5  # Segundos entre cada medición de distancia
        self.ultima_medicion_distancia = time.time()
        self.sensors_initialized = True

    def draw_buttons(self):
        """Draw the two main buttons on the screen using the custom font."""
        # Clear screen with cyan background
        self.display.clear(self.CYAN)

        # Draw Diagnostico button (button area: x=10, y=50 to x=210, y=90)
        self.display.fill_rectangle(10, 50, 200, 40, self.BLUE)
        self.display.draw_text(20, 60, 'Diagnostico:', self.font, self.BLACK, self.BLUE)

        # Draw Informacion button (button area: x=10, y=120 to x=210, y=160)
        self.display.fill_rectangle(10, 120, 200, 40, self.BLUE)
        self.display.draw_text(20, 130, 'Informacion:', self.font, self.BLACK, self.BLUE)

    def draw_information_menu(self):
        """Draw the information submenu with multiple options."""
        self.display.clear(self.BLUE)

        options = [
            
            'RCP',
            'Control de hemorragias',
            'Maniobra de Heimlich',
            'Vendaje de heridas',
            'Manejo de quemaduras',
            'Exploracion primaria',
            'Numeros de emergencia'
        ]
        
            # Define button dimensions and spacing
        button_height = 25  # Reduced height for buttons
        button_spacing = 10  # Spacing between buttons

        # Draw each option as a button
        for i, option in enumerate(options):
            y_position = 30 + i * (button_height + button_spacing)
            self.display.fill_rectangle(5, y_position, 228, button_height, self.LIGHT_BLUE)
            self.display.draw_text(7, y_position + 5, option, self.font, self.BLACK, self.LIGHT_BLUE)

        # Draw Atras button
        self.display.fill_rectangle(5, 30 + len(options) * (button_height + button_spacing), 228, button_height, self.LIGHT_BLUE)
        self.display.draw_text(80, 30 + len(options) * (button_height + button_spacing) + 5, 'Atras:', self.font, self.BLACK, self.LIGHT_BLUE)

    def draw_back_screen(self, message):
        """Draw the message and the back button on the screen."""
        # Clear screen with cyan background
        self.display.clear(self.CYAN)

        # Display the selected option message
        self.display.draw_text(10, 100, message, self.font, self.BLACK, self.CYAN)

        # Draw Atras button (button area: x=10, y=200 to x=210, y=240)
        self.display.fill_rectangle(10, 200, 200, 40, self.LIGHT_BLUE)
        self.display.draw_text(80, 210, 'Atras:', self.font, self.BLACK, self.LIGHT_BLUE)
        
    def paginate_text(self, text, max_width, max_lines):
        """Divide el texto en páginas, cada una con un máximo de líneas permitidas."""
        # Split the text by new lines
        paragraphs = text.split('\n')
        lines = []

        for paragraph in paragraphs:
            # Split each paragraph into lines based on width
            words = paragraph.split()
            current_line = ''
            for word in words:
                # Check if adding the next word would exceed the max width
                if len(current_line + ' ' + word) * self.CHAR_WIDTH <= max_width:
                    current_line += (' ' + word if current_line else word)
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)
            
            # Add an empty line after each paragraph
            lines.append('')

        # Divide lines into pages
        paginated_text = [lines[i:i + max_lines] for i in range(0, len(lines), max_lines)]
        return paginated_text
    
    def wrap_text(self, text, max_width):
        """Wrap text to fit within max_width and handle specific bullet points."""
        # Split the text by new lines
        paragraphs = text.split('\n')
        lines = []

        for paragraph in paragraphs:
            # Split each paragraph into lines based on width
            words = paragraph.split()
            current_line = ''
            for word in words:
                # Check if adding the next word would exceed the max width
                if len(current_line + ' ' + word) * self.CHAR_WIDTH <= max_width:
                    current_line += (' ' + word if current_line else word)
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)
            
            # Add an empty line after each paragraph
            lines.append('')

        return lines

    def draw_step(self, steps):
        """Dibuja el paso actual de las instrucciones en la pantalla, con paginación."""
        if self.current_step < len(steps):
            self.display.clear(self.CYAN)

            # Paginación del texto del paso actual
            paginated_text = self.paginate_text(steps[self.current_step], self.MAX_WIDTH, 16)

            # Mostrar el contenido de la página actual
            y = 30
            line_spacing = 15  # Ajusta el espaciado entre líneas aquí

            for line in paginated_text[self.current_page]:
                self.display.draw_text(10, y, line, self.font, self.BLACK, self.CYAN)
                y += line_spacing  # Cambia el espaciado vertical entre líneas

            # Mostrar botones de navegación según la página actual
            if self.current_page > 0:  # Mostrar botón "Anterior" si no estamos en la primera página
                self.display.fill_rectangle(10, self.display.height - 40, 100, 30, self.LIGHT_BLUE)
                self.display.draw_text(20, self.display.height - 35, 'Anterior', self.font, self.BLACK, self.LIGHT_BLUE)

            if len(paginated_text) > self.current_page + 1:  # Mostrar botón "Siguiente" si hay más páginas
                self.display.fill_rectangle(self.display.width - 110, self.display.height - 40, 100, 30, self.LIGHT_BLUE)
                self.display.draw_text(self.display.width - 100, self.display.height - 35, 'Siguiente', self.font, self.BLACK, self.LIGHT_BLUE)
        else:
            self.display.clear(self.CYAN)
            self.display.draw_text(10, 100, 'Finalizado.', self.font, self.BLACK, self.CYAN)

            # Agregar botón para volver al menú principal
            self.display.fill_rectangle(10, 200, 200, 40, self.LIGHT_BLUE)
            self.display.draw_text(20, 210, 'Menu Principal:', self.font, self.BLACK, self.LIGHT_BLUE)

    def touch_interrupt(self, x, y):
        """Procesar eventos de interrupción de la pantalla táctil."""
        if x is not None and y is not None:
            y = (self.display.height - 1) - y

            if self.main_menu:
                if 10 <= x <= 210 and 50 <= y <= 90:  # Diagnostico button
                    self.main_menu = False
                    self.in_option_screen = True
                    if not self.sensors_initialized:
                        self.init_sensors()
                    self.start_diagnostics()
                elif 10 <= x <= 210 and 120 <= y <= 160:  # Informacion button
                    self.main_menu = False
                    self.in_information_menu = True
                    self.draw_information_menu()
            elif self.in_information_menu:
                if 5 <= x <= 233 and 30 <= y <= 270:  # Any option pressed
                    option_index = (y - 30) // 35
                    options = [
                        'RCP',
                        'Control de hemorragias',
                        'Maniobra de Heimlich',
                        'Vendaje de heridas',
                        'Manejo de quemaduras',
                        'Exploracion primaria',
                        'Numeros de emergencia'
                    ]
                    if option_index < len(options):
                        selected_option = options[option_index]
                        if selected_option == 'Exploracion primaria':
                            self.in_information_menu = False
                            self.current_step = 0
                            self.current_page = 0
                            self.current_info_type = 'exploracion'
                            self.draw_step(exploration_steps)
                        elif selected_option == 'Manejo de quemaduras':
                            self.in_information_menu = False
                            self.current_step = 0
                            self.current_page = 0
                            self.current_info_type = 'quemaduras'
                            self.draw_step(burn_steps)
                        elif selected_option == 'Vendaje de heridas':
                            self.in_information_menu = False
                            self.current_step = 0
                            self.current_page = 0
                            self.current_info_type = 'vendaje'
                            self.draw_step(steps)
                        elif selected_option == 'Maniobra de Heimlich':
                            self.in_information_menu = False
                            self.current_step = 0
                            self.current_page = 0
                            self.current_info_type = 'atoramiento'
                            self.draw_step(choking_steps)
                        elif selected_option == 'Numeros de emergencia':
                            self.in_information_menu = False
                            self.current_step = 0
                            self.current_page = 0
                            self.current_info_type = 'emergencia'
                            self.draw_step(emergency_steps)
                        elif selected_option == 'RCP':
                            self.in_information_menu = False
                            self.current_step = 0
                            self.current_page = 0
                            self.current_info_type = 'rcp'
                            self.draw_step(rcp_steps)
                        elif selected_option == 'Control de hemorragias':
                            self.in_information_menu = False
                            self.current_step = 0
                            self.current_page = 0
                            self.current_info_type = 'hemorragia'
                            self.draw_step(hemorrhage_steps)
                        else:
                            self.in_information_menu = False
                            self.in_option_screen = True
                            self.draw_back_screen(selected_option)
                elif 5 <= x <= 233 and 270 <= y <= 300:  # Atras button in information menu
                    self.in_information_menu = False
                    self.main_menu = True
                    self.draw_buttons()
            elif self.in_option_screen:
                if 10 <= x <= 210 and 200 <= y <= 240:  # Atras button in option screen
                    self.in_option_screen = False
                    self.in_information_menu = True
                    self.draw_information_menu()
            else:
                # Aquí manejamos la vista de pasos para RCP y otras opciones
                current_steps = exploration_steps if self.current_info_type == 'exploracion' else (
                    burn_steps if self.current_info_type == 'quemaduras' else (
                        steps if self.current_info_type == 'vendaje' else (
                            choking_steps if self.current_info_type == 'atoramiento' else (
                                rcp_steps if self.current_info_type == 'rcp' else (
                                    emergency_steps if self.current_info_type == 'emergencia' else hemorrhage_steps
                                )
                            )
                        )
                    )
                )
                if 10 <= x <= 210 and 200 <= y <= 240:  # Atras button in step view
                    if self.current_step < len(current_steps) - 1:
                        self.current_step += 1
                        self.current_page = 0
                        self.draw_step(current_steps)
                    else:
                        self.in_information_menu = True
                        self.current_step = 0
                        self.current_info_type = None
                        self.draw_information_menu()
                elif 10 <= x <= 110 and self.display.height - 40 <= y <= self.display.height - 10:  # Anterior button
                    if self.current_page > 0:
                        self.current_page -= 1
                        self.draw_step(current_steps)
                elif self.display.width - 110 <= x <= self.display.width - 10 and self.display.height - 40 <= y <= self.display.height - 10:  # Siguiente button
                    paginated_text = self.paginate_text(current_steps[self.current_step], self.MAX_WIDTH, 12)
                    if len(paginated_text) > self.current_page + 1:
                        self.current_page += 1
                        self.draw_step(current_steps)
                        
    def start_diagnostics(self):
        """Iniciar el proceso de diagnóstico."""
        self.display.clear(self.CYAN)
        self.display.draw_text(10, 20, 'Iniciando diagnostico...', self.font, self.BLACK, self.CYAN)
        self.display.draw_text(10, 200, 'Toque para volver', self.font, self.BLACK, self.CYAN)

        measurement_count = 0
        max_measurements = 5  # Número máximo de mediciones antes de volver al menú
        last_update_time = time.time()
        update_interval = 0.5
        
        while True:
            try:
                tiempo_actual = time.time()
                # Lectura del sensor MAX30102
                self.sensor_max.check()
                if self.sensor_max.available():
                    red_reading = self.sensor_max.pop_red_from_storage()
                    ir_reading = self.sensor_max.pop_ir_from_storage()
                    if red_reading < self.NO_FINGER_THRESHOLD:
                        self.display_no_finger()
                        continue
                    self.red_buf.append(red_reading)
                    self.ir_buf.append(ir_reading)
                    self.counter += 1
                    if self.counter >= self.limit:
                        result = hrcalc.calc_hr_and_spo2(self.ir_buf, self.red_buf)
                        hr = result[0] if result[1] else 'Error'
                        spo2 = result[2] if result[3] else 'Error'
                        
                        if self.sensor_temp is not None:
                            temp_objeto = self.sensor_temp.object_temp
                        else:
                            temp_objeto = None
                        # Actualizar la pantalla solo si ha pasado el intervalo
                        if tiempo_actual - last_update_time >= update_interval:
                            self.display_data(hr, spo2, temp_objeto)
                            last_update_time = tiempo_actual
                        self.counter = 0
                        self.red_buf = []
                        self.ir_buf = []
                        
                        measurement_count += 1
                        
                        if measurement_count >= max_measurements:
                            self.display.clear(self.CYAN)
                            self.display.draw_text(10, 100, 'Diagnostico completado', self.font, self.BLACK, self.CYAN)
                            self.display.draw_text(10, 130, 'Volviendo al menu...', self.font, self.BLACK, self.CYAN)
                            time.sleep(2)
                            self.main_menu = True
                            self.in_option_screen = False
                            self.draw_buttons()
                            return

                # Verificar si se ha tocado la pantalla para volver
                if self.touch.raw_touch():
                    self.main_menu = True
                    self.in_option_screen = False
                    self.draw_buttons()
                    return

            except Exception as e:
                print("Error:", e)
                self.led.off()
                time.sleep(1)
        
        

    def calculate_bpm(self, t_start, value, beat, threshold_on, threshold_off):
        if value > 1000:
            if not beat and value > threshold_on:
                beat = True
                t_us = time.ticks_diff(time.ticks_us(), t_start)
                t_s = t_us / 1000000
                bpm = (1 / t_s) * 60
                if bpm < 300:
                    t_start = time.ticks_us()
                    return round(bpm, 2), t_start, beat
            if beat and value < threshold_off:
                beat = False
        return None, t_start, beat

    def display_data(self, bpm, spo2, temp_objeto):
        """Mostrar BPM, SpO2 y temperatura en pantalla, e indicar el estado de salud"""
        self.display.clear(self.CYAN)
        
        # Colores
        DARK_GREEN = color565(0, 128, 0)
        RED = color565(255, 0, 0)
        
        # Función para determinar el color basado en el valor
        def get_color(value, normal_range):
            return DARK_GREEN if normal_range[0] <= value <= normal_range[1] else RED
        
        # Mostrar frecuencia cardíaca
        self.display.draw_text(10, 20, 'Frecuencia Cardiaca:', self.font, self.BLACK, self.CYAN)
        bpm_color = get_color(bpm, (60, 100)) if isinstance(bpm, (int, float)) else self.BLACK
        self.display.draw_text(10, 40, '{} BPM'.format(bpm), self.font, bpm_color, self.CYAN)
        
        # Mostrar saturación de oxígeno
        self.display.draw_text(10, 70, 'Saturacion Oxigeno:', self.font, self.BLACK, self.CYAN)
        spo2_color = get_color(spo2, (95, 100)) if isinstance(spo2, (int, float)) else self.BLACK
        self.display.draw_text(10, 90, '{} %'.format(spo2), self.font, spo2_color, self.CYAN)
        
        # Mostrar temperatura (rango ampliado)
        self.display.draw_text(10, 120, 'Temperatura:', self.font, self.BLACK, self.CYAN)
        if self.sensor_temp is not None and isinstance(temp_objeto, (int, float)):
            temp_color = get_color(temp_objeto, (35.5, 37.5))  # Rango ampliado
            self.display.draw_text(10, 140, '{:.1f} C'.format(temp_objeto), self.font, temp_color, self.CYAN)
        else:
            self.display.draw_text(10, 140, 'No disponible', self.font, self.BLACK, self.CYAN)
        
        # Evaluación general de salud
        health_status = "NORMAL"
        if (isinstance(bpm, (int, float)) and (bpm < 60 or bpm > 100)) or \
           (isinstance(spo2, (int, float)) and spo2 < 95) or \
           (isinstance(temp_objeto, (int, float)) and (temp_objeto < 35.5 or temp_objeto > 37.5)):
            health_status = "REVISAR"
        
        # Mostrar estado de salud
        status_color = DARK_GREEN if health_status == "NORMAL" else RED
        self.display.draw_text(10, 170, 'Estado:', self.font, self.BLACK, self.CYAN)
        self.display.draw_text(10, 190, health_status, self.font, status_color, self.CYAN)

    def display_no_finger(self):
        """Mostrar mensaje de 'No finger detected' en pantalla"""
        self.display.clear(color565(255, 0, 0))  # Limpiar la pantalla con color rojo
        self.display.draw_text(10, 80, 'No finger detected', self.font, color565(255, 255, 255), color565(255, 0, 0))
        time.sleep(1)
        
    def medir_distancia(self):
        print("Starting distance measurement")
        self.trigger.value(0)
        time.sleep_us(2)
        self.trigger.value(1)
        time.sleep_us(10)
        self.trigger.value(0)
        print("Trigger pulse sent")

        # Wait for echo to go high
        pulse_start = time.ticks_us()
        timeout = time.ticks_add(pulse_start, 100000)  # 100ms timeout
        while self.echo.value() == 0:
            if time.ticks_diff(timeout, time.ticks_us()) <= 0:
                print("Timeout waiting for echo to go high")
                return float('inf')
        pulse_start = time.ticks_us()
        print(f"Echo went high at {pulse_start}")

        # Wait for echo to go low
        timeout = time.ticks_add(pulse_start, 100000)  # 100ms timeout
        while self.echo.value() == 1:
            if time.ticks_diff(timeout, time.ticks_us()) <= 0:
                print("Timeout waiting for echo to go low")
                return float('inf')
        pulse_end = time.ticks_us()
        print(f"Echo went low at {pulse_end}")

        duracion = time.ticks_diff(pulse_end, pulse_start)
        distancia_cm = (duracion / 2) / 29.1
        print(f"Pulse duration: {duracion} us")
        print(f"Calculated distance: {distancia_cm:.2f} cm")
        return distancia_cm
        pass
    
    def mostrar_mensaje_byul(self):
        self.display.clear(color565(0, 255, 255))  # Fondo cyan
        self.display.draw_text(50, 120, 'Hola, soy Byul', self.font, color565(0, 0, 0), color565(0, 255, 255))
    
    def pantalla_negra(self):
        self.display.clear(color565(0, 0, 0)) 
    
    def run(self):
        """Run the demo."""
        while True:
            idle()
            
    def manejar_proximidad(self):
        DISTANCE_THRESHOLD = 60
        CONSECUTIVE_READINGS = 5
        READING_INTERVAL = 0.1  # Reduced to 0.1 seconds for faster response

        close_readings = 0
        for _ in range(CONSECUTIVE_READINGS):
            distance = self.medir_distancia()
            if distance < DISTANCE_THRESHOLD and distance != float('inf'):
                close_readings += 1
            time.sleep(READING_INTERVAL)

        return close_readings >= 3  
            
    def run(self):
        PROXIMITY_CHECK_INTERVAL = 0.5  # Check proximity every 0.5 seconds
        last_proximity_check = time.time()
        someone_detected = False
        consecutive_detections = 0
        consecutive_non_detections = 0

        while True:
            current_time = time.time()

            if current_time - last_proximity_check >= PROXIMITY_CHECK_INTERVAL:
                is_someone_close = self.manejar_proximidad()
                last_proximity_check = current_time

                if is_someone_close:
                    consecutive_detections += 1
                    consecutive_non_detections = 0
                else:
                    consecutive_non_detections += 1
                    consecutive_detections = 0

                if consecutive_detections >= 2 and not someone_detected:
                    # Someone just arrived
                    print("Persona detectada")
                    self.mostrar_mensaje_byul()
                    time.sleep(2)
                    self.draw_buttons()
                    someone_detected = True
                elif consecutive_non_detections >= 4 and someone_detected:
                    # Person left
                    print("Persona se fue")
                    self.pantalla_negra()
                    someone_detected = False

            if someone_detected:
                # Process touch events and handle menu logic
                touch_data = self.touch.get_touch()
                if touch_data is not None:
                    x, y = touch_data
                    self.touch_interrupt(x, y)

                # Handle menu and screen logic
                if self.in_option_screen:
                    # Logic for option screen
                    pass
                elif self.in_information_menu:
                    # Logic for information menu
                    pass

            time.sleep(0.1)
   

