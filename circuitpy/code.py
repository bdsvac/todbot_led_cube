import board
import busio
import neopixel
import os
import terminalio
import time
import adafruit_esp32spi.adafruit_esp32spi_wifimanager as wifimanager
import adafruit_esp32spi.adafruit_esp32spi_wsgiserver as server
from adafruit_esp32spi import adafruit_esp32spi
from SimpleWSGIApplication import SimpleWSGIApplication
from WiFiManager import WiFiManager
from adafruit_led_animation.animation.rainbowsparkle import RainbowSparkle
from adafruit_led_animation.animation.rainbow import Rainbow
from adafruit_led_animation.animation.rainbowchase import RainbowChase
from adafruit_led_animation.animation.rainbowcomet import RainbowComet
from adafruit_led_animation.animation.blink import Blink
from adafruit_led_animation.animation.solid import Solid
from adafruit_led_animation.animation.colorcycle import ColorCycle
from adafruit_led_animation.animation.chase import Chase
from adafruit_led_animation.animation.comet import Comet
from adafruit_led_animation.animation.pulse import Pulse
from adafruit_led_animation.color import MAGENTA, ORANGE, TEAL, WHITE

try:
    import json as json_module
except ImportError:
    import ujson as json_module

leds = neopixel.NeoPixel(board.D6,64*5,brightness=0.1,auto_write=False)
leds.fill((0, 0, 255))
leds.show()
current = None
current_color = (0, 0, 255)
color_list = [MAGENTA, ORANGE, TEAL]

rainbow_sparkle = RainbowSparkle(leds, speed=0.1, num_sparkles=15)
rainbow = Rainbow(leds, speed=0.1, period=2)
rainbow_chase = RainbowChase(leds, speed=0.1, size=3, spacing=6)
rainbow_comet = RainbowComet(leds, speed=0.1, tail_length=7, bounce=True)
colorcycle = ColorCycle(leds, 0.5, colors=color_list)
chase = Chase(leds, speed=0.1, color=current_color, size=3, spacing=6)
solid = Solid(leds, color=current_color)
blink = Blink(leds, speed=0.5, color=current_color)
comet = Comet(leds, speed=0.01, color=current_color, tail_length=10, bounce=True)
pulse = Pulse(leds, speed=0.1, color=current_color, period=3)

spi = board.SPI()
wm = WiFiManager(spi)
esp = None
try:
    esp = wm.GetEsp()
except ConnectionError:
    pass

# Our HTTP Request handlers
def led_on(environ):  # pylint: disable=unused-argument
    global current, current_color
    print("led on!")
    leds.fill(current_color)
    leds.show()
    current = None
    return ("200 OK", [], [])

def led_off(environ):  # pylint: disable=unused-argument
    global current
    print("led off!")
    leds.fill(0)
    leds.show()
    current = None
    return ("200 OK", [], [])

def led_color(environ):  # pylint: disable=unused-argument
    global current, current_color
    json = json_module.loads(environ["wsgi.input"].getvalue())
    print(json)
    rgb_tuple = (json.get("r"), json.get("g"), json.get("b"))
    current_color = rgb_tuple
    current.color = current_color
    #leds.fill(rgb_tuple)
    #leds.show()
    #current = None
    return ("200 OK", [], [])

def set_rainbow_sparkle(environ):  # pylint: disable=unused-argument
    global current, rainbow_sparkle
    current = rainbow_sparkle
    return ("200 OK", [], [])

def set_rainbowchase(environ):  # pylint: disable=unused-argument
    global current, rainbow_chase
    current = rainbow_chase
    return ("200 OK", [], [])

def set_rainbowcomet(environ):  # pylint: disable=unused-argument
    global current, rainbow_comet
    current = rainbow_comet
    return ("200 OK", [], [])

def set_rainbow(environ):  # pylint: disable=unused-argument
    global current, rainbow
    current = rainbow
    return ("200 OK", [], [])

def set_colorcycle(environ):  # pylint: disable=unused-argument
    global current, colorcycle
    current = colorcycle
    return ("200 OK", [], [])

def set_chase(environ):  # pylint: disable=unused-argument
    global current, chase, current_color
    if (current_color is not None):
        chase.color = current_color
    current = chase
    return ("200 OK", [], [])

def set_solid(environ):  # pylint: disable=unused-argument
    global current, solid
    if (current_color is not None):
        solid.color = current_color
    current = solid
    return ("200 OK", [], [])

def set_blink(environ):  # pylint: disable=unused-argument
    global current, blink
    if (current_color is not None):
        blink.color = current_color
    current = blink
    return ("200 OK", [], [])

def set_comet(environ):  # pylint: disable=unused-argument
    global current, blink
    if (current_color is not None):
        comet.color = current_color
    current = comet
    return ("200 OK", [], [])

def set_pulse(environ):  # pylint: disable=unused-argument
    global current, pulse
    if (current_color is not None):
        pulse.color = current_color
    current = pulse
    return ("200 OK", [], [])

# Here we create our application, setting the static directory location
# and registering the above request_handlers for specific HTTP requests
# we want to listen and respond to.
static = "/static"
try:
    static_files = os.listdir(static)
    if "index.html" not in static_files:
        raise RuntimeError(
            """
            This example depends on an index.html, but it isn't present.
            Please add it to the {0} directory""".format(
                static
            )
        )
except (OSError) as e:
    raise RuntimeError(
        """
        This example depends on a static asset directory.
        Please create one named {0} in the root of the device filesystem.""".format(
            static
        )
    )

web_app = SimpleWSGIApplication(static_dir=static)
web_app.on("GET", "/led_on", led_on)
web_app.on("GET", "/led_off", led_off)
web_app.on("POST", "/ajax/ledcolor", led_color)
web_app.on("GET", "/rainbowsparkle", set_rainbow_sparkle)
web_app.on("GET", "/colorcycle", set_colorcycle)
web_app.on("GET", "/chase", set_chase)
web_app.on("GET", "/solid", set_solid)
web_app.on("GET", "/blink", set_blink)
web_app.on("GET", "/comet", set_comet)
web_app.on("GET", "/pulse", set_pulse)
web_app.on("GET", "/rainbow", set_rainbow)
web_app.on("GET", "/rainbowchase", set_rainbowchase)
web_app.on("GET", "/rainbowcomet", set_rainbowcomet)

# Here we setup our server, passing in our web_app as the application
if (esp):
    current = rainbow_chase
    server.set_interface(esp)
    wsgiServer = server.WSGIServer(80, application=web_app)
    print("open this IP in your browser: ", esp.pretty_ip(esp.ip_address))
    wsgiServer.start()
else:
    current = rainbow

while True:
    # Our main loop where we have the server poll for incoming requests
    try:
        if (esp):
            wsgiServer.update_poll()
        if (current is not None):
            current.animate(show=False)
            leds.show()
    except (ValueError, RuntimeError) as e:
        print("Failed to update server, restarting ESP32\n", e)
        wm.EnsureConnection()
        continue
