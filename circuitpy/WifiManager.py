import adafruit_requests
import board
import gc
import time

try:
    import ipaddress
    import socketpool
    import ssl
    import wifi
except ImportError:
    pass

try:
    import adafruit_esp32spi.adafruit_esp32spi_socket as socket
    from adafruit_esp32spi import adafruit_esp32spi
except ImportError:
    pass

from adafruit_io.adafruit_io import IO_HTTP, AdafruitIO_RequestError
from digitalio import DigitalInOut

try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")

class WiFiManager:
    def __init__(self, spi = None):
        self.usingSpi = False
        if (spi is not None):
            self.usingSpi = True
            esp32_cs = DigitalInOut(board.D13)
            esp32_busy = DigitalInOut(board.D11)
            esp32_reset = DigitalInOut(board.D12)
            self.esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_busy, esp32_reset)
            socket.set_interface(self.esp)
            adafruit_requests.set_socket(socket, self.esp)
        else:
            pool = socketpool.SocketPool(wifi.radio)
            self.requests = adafruit_requests.Session(pool, ssl.create_default_context())

    def GetEsp(self):
        self.EnsureConnection()
        if (self.usingSpi):
            return self.esp
        return None

    def EnsureConnection(self):
        if (self.usingSpi):
            while not self.esp.is_connected:
                try:
                    print("Ensuring WiFi Connection.")
                    self.esp.connect_AP(secrets["ssid"], secrets["password"])
                    print("WiFi Connected.")
                except RuntimeError as e:
                    print("could not connect to AP, retrying: ", e)
                    time.sleep(2)
        else:
            while wifi.radio.ap_info is None:
                try:
                    print("Ensuring WiFi Connection.")
                    wifi.radio.connect(secrets["ssid"], secrets["password"])
                    print("WiFi Connected.")
                except RuntimeError as e:
                    print("could not connect to AP, retrying: ", e)
                    time.sleep(2)


    def ScanNetworks(self):
        if (self.usingSpi):
            if self.esp.status == adafruit_esp32spi.WL_IDLE_STATUS:
                print("ESP32 WiFi Test")
                print("Firmware version: ", self.esp.firmware_version)
                print("MAC addr:", [hex(i) for i in self.esp.MAC_address])
            print("Available WiFi networks:")
            for ap in self.esp.scan_networks():
                print("\t%s\t\tRSSI: %d\tChannel: %d" % (str(ap['ssid'], 'utf-8'),
                        ap['rssi'], ap['channel']))
        else:
            print("ESP32-S2 WiFi Test")
            print("MAC addr:", [hex(i) for i in wifi.radio.mac_address])
            print("Available WiFi networks:")
            for network in wifi.radio.start_scanning_networks():
                print("\t%s\t\tRSSI: %d\tChannel: %d" % (str(network.ssid, "utf-8"),
                        network.rssi, network.channel))
            wifi.radio.stop_scanning_networks()

    def GetOutsideTemp(self):
        self.EnsureConnection()
        JSON_URL = "http://api.openweathermap.org/data/2.5/weather?q=" + secrets["openweather_location"] + "&appid=" + secrets["openweather_token"] + "&units=metric"
        r = None
        if (self.usingSpi):
            r = adafruit_requests.get(JSON_URL)
        else:
            r = self.requests.get(JSON_URL)
        #print(r.json()['main'])
        #{'temp_min': -5.25, 'pressure': 1011, 'feels_like': -5.3, 'humidity': 81, 'temp_max': -1.79, 'temp': -3.37}
        c = float(r.json()['main']['temp'])
        f = (c * 9/5) + 32
        fStr = str(round(f))
        r.close()
        r = None
        gc.collect()
        return fStr + " F"

    def GetInsideTemps(self):
        self.EnsureConnection()
        io = None
        if (self.usingSpi):
            io = IO_HTTP(secrets["aio_username"], secrets["aio_key"], adafruit_requests)
        else:
            io = IO_HTTP(secrets["aio_username"], secrets["aio_key"], self.requests)

        aio_feed0_name = "upstairs"
        aio_feed1_name = "downstairs"
        aio_feed2_name = "basement"

        feed0 = None
        feed1 = None
        feed2 = None

        if (feed0 is None):
            try:
                feed0 = io.get_feed(aio_feed0_name)
            except:
                print("Can't get " + aio_feed0_name + " feed.")
        if (feed1 is None):
            try:
                feed1 = io.get_feed(aio_feed1_name)
            except:
                print("Can't get " + aio_feed1_name + " feed.")
        if (feed2 is None):
            try:
                feed2 = io.get_feed(aio_feed2_name)
            except:
                print("Can't get " + aio_feed2_name + " feed.")

        try:
            t0 = io.receive_data(feed0["key"])
            t1 = io.receive_data(feed1["key"])
            t2 = io.receive_data(feed2["key"])

            feed0 = None
            feed1 = None
            feed2 = None
            io = None
            gc.collect()

            return t0["value"], t1["value"], t2["value"]
        except:
            return None, None, None

    def get_strftime(self, time_format, location=None):
            TIME_SERVICE = (
                "https://io.adafruit.com/api/v2/%s/integrations/time/strftime?x-aio-key=%s"
            )
            api_url = None
            reply = None
            try:
                aio_username = secrets["aio_username"]
                aio_key = secrets["aio_key"]
            except KeyError:
                raise KeyError("\n\nOur time service requires a login/password to rate-limit. Please register for a free adafruit.io account and place the user/key in your secrets file under 'aio_username' and 'aio_key'") from KeyError

            if location is None:
                location = secrets.get("timezone", location)
            if location is None:
                location = "America/Menominee"

            if location:
                api_url = (TIME_SERVICE + "&tz=%s") % (aio_username, aio_key, location)
            else:  # we'll try to figure it out from the IP address
                api_url = TIME_SERVICE % (aio_username, aio_key)
            api_url += "&fmt=" + self.url_encode(time_format)

            try:
                response = None
                if (self.usingSpi):
                    response = adafruit_requests.get(api_url, timeout=10)
                else:
                    response = self.requests.get(api_url, timeout=10)
                if response.status_code != 200:
                    print(response)
                    error_message = (
                        "Error connecting to Adafruit IO. The response was: " + response.text
                    )
                    raise RuntimeError(error_message)
                reply = response.text
            except KeyError:
                raise KeyError(
                    "Was unable to lookup the time, try setting secrets['timezone'] according to http://worldtimeapi.org/timezones"  # pylint: disable=line-too-long
                ) from KeyError
            response.close()
            response = None
            gc.collect()
            return reply

    def get_local_time(self, location=None, rtc=None):
        self.EnsureConnection()
        aio_username = secrets["aio_username"]
        aio_key = secrets["aio_key"]
        TIME_URL = "https://io.adafruit.com/api/v2/%s/integrations/time/strftime?x-aio-key=%s" % (aio_username, aio_key)
        TIME_URL += "&fmt=%25Y-%25m-%25d+%25H%3A%25M%3A%25S.%25L+%25j+%25u+%25z+%25Z"
        TIME_SERVICE = (
        "https://io.adafruit.com/api/v2/%s/integrations/time/strftime?x-aio-key=%s"
        )
        TIME_SERVICE_FORMAT = "%Y-%m-%d %H:%M:%S.%L %j %u %z %Z"
        reply = self.get_strftime(TIME_SERVICE_FORMAT, location=location)
        if reply:
            times = reply.split(" ")
            the_date = times[0]
            the_time = times[1]
            year_day = int(times[2])
            week_day = int(times[3])
            is_dst = None  # no way to know yet
            year, month, mday = [int(x) for x in the_date.split("-")]
            the_time = the_time.split(".")[0]
            hours, minutes, seconds = [int(x) for x in the_time.split(":")]
            now = time.struct_time(
                (year, month, mday, hours, minutes, seconds, week_day, year_day, is_dst)
            )
            if rtc is not None:
                print("setting rtc")
                rtc.datetime = now
        return reply

    def url_encode(self, url):
        url = url.replace(" ", "+")
        url = url.replace("%", "%25")
        url = url.replace(":", "%3A")
        return url




