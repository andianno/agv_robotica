from modules.connection.coppelia_connector import CoppeliaConnector
from modules.sensors.generic_sensor import GenericSensor
import threading

SENSORS_KEY = "body_memory"

class ColorSensor(GenericSensor):
    STEPS_PER_READ = 1   # 20Hz se il passo fisico è 50ms

    def __init__(self, name, clock):
        """Initialize a clock-synchronized color sensor.

        Args:
            name: CoppeliaSim object name used to resolve the vision sensor
                handle.
            clock: :class:`SimClock` instance used to schedule readings and
                acknowledge completed simulation steps.

        Returns:
            None.
        """
        super().__init__(name)
        self.clock = clock

        self.connector = CoppeliaConnector(name=f"{self.name}")
        self.sim = self.connector.get_sim()

        try:
            self.handle = self.sim.getObject(self.name)
        except Exception as e:
            print(f"[{self.name}] ERRORE: Sensore non trovato in CoppeliaSim. Dettagli: {e}")
            self.handle = None

        self._running = False
        self._thread = None
        self.last_color = 0.0
        self.last_step_tag = None

    def start(self):
        """Start the clock-synchronized color-reading thread.

        Returns:
            None. Calling this method while the sensor is already running has
            no effect.
        """
        if not self._running:
            self._running = True
            next_step = self.clock.register(self.name, self.STEPS_PER_READ)
            self._thread = threading.Thread(target=self._loop_lettura, args=(next_step,), daemon=True)
            self._thread.start()
            print(f"[{self.name}] Thread avviato.")

    def _loop_lettura(self, next_step):
        """Read the sensor at each scheduled simulation step.

        Args:
            next_step: First simulation step at which a reading is due,
                returned by ``SimClock.register``.

        Returns:
            None. The loop exits when ``_running`` becomes ``False``.
        """
        while self._running:
            actual = self.clock.wait_until(next_step)
            if not self._running:
                break
            self.read()
            self.last_step_tag = actual
            self.clock.ack(self.name)
            next_step = actual + self.STEPS_PER_READ

    def read(self):
        """Read and cache the current percentage of black pixels.

        Returns:
            float: Black-pixel ratio in the range from ``0.0`` to ``1.0``.
        """
        color_val = self.get_black_percentage()
        self.last_color = color_val
        return color_val

    def get_black_percentage(self):
        """Calculate the percentage of black pixels in the sensor image.

        Pixels whose red, green, and blue channels are all at most 30 are
        classified as black.

        Returns:
            float: Ratio of black pixels in the range from ``0.0`` to ``1.0``.
            Returns ``0.0`` when the image contains no pixels.
        """
        res, p1, p2 = self.sim.handleVisionSensor(self.handle)
        img, res = self.sim.getVisionSensorImg(self.handle)
        count = 0
        total_pixels = res[0] * res[1]
        for i in range(total_pixels):
            r = img[i*3]
            g = img[i*3 + 1]
            b = img[i*3 + 2]
            if r <= 30 and g <= 30 and b <= 30:
                count += 1
        return (count / total_pixels) if total_pixels > 0 else 0

    def stop(self):
        """Stop the color-reading thread and unregister the clock participant.

        Returns:
            None. The method waits for the worker thread to finish when it has
            been started.
        """
        self._running = False
        self.clock.unregister(self.name)
        if self._thread:
            self._thread.join()
            print(f"[{self.name}] Thread fermato.")