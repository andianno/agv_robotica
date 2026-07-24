from modules.connection.coppelia_connector import CoppeliaConnector
from modules.sensors.generic_sensor import GenericSensor
from modules.connection.redis_interface import RedisInterface
import threading
import time

class LidarSensor(GenericSensor):
    def __init__(self, name):
        """Initialize the LiDAR sensor and its simulator and Redis handles.

        Args:
            name: CoppeliaSim object name used to resolve the proximity
                sensor handle.

        Returns:
            None.

        Raises:
            ConnectionError: If Redis is unavailable during initialization.
        """
        super().__init__(name)

        # 1. Connessione a CoppeliaSim (Isolata e sicura grazie al Multiton)
        self.connector = CoppeliaConnector(name=f"{self.name}")
        self.sim = self.connector.get_sim()

        # Recuperiamo l'handle dell'oggetto da CoppeliaSim
        try:
            self.handle = self.sim.getObject(self.name)
        except Exception as e:
            print(f"[{self.name}] ERRORE: Sensore non trovato in CoppeliaSim. Dettagli: {e}")
            self.handle = None

        # 2. Connessione a Redis (Condivisa e sicura grazie al Singleton)
        self.redis_client = RedisInterface()
        if not self.redis_client.db:
            print(f"[{self.name}] Redis non raggiungibile.")
            raise ConnectionError("Redis err")

        self.last_data = {"ostacolo": False, "distanza": 999.0}
        self.frequenza_lettura = 0.05  
        self._running = False
        self._thread = None
        self.soglia_sicurezza = 2.0  

    def start(self):
        """Start the background LiDAR-reading thread.

        Returns:
            None. Calling this method while the sensor is already running has
            no effect.
        """
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._loop_lettura, daemon=True)
            self._thread.start()
            print(f"[{self.name}] 🟢 Thread avviato in modalità REALE.")

 
    def _loop_lettura(self):
        """Continuously read proximity data and publish obstacle state.

        The loop stores the latest obstacle flag and distance in
        ``last_data`` and publishes ``ostacolo_lidar`` to Brain memory.

        Returns:
            None. The loop exits when ``_running`` becomes ``False``.
        """
        while self._running:
            try:
                result, distance = self.read_distanza()
                ostacolo = bool(
                    result and distance is not None and distance < self.soglia_sicurezza
                )
                self.last_data = {
                    "ostacolo": ostacolo,
                    "distanza": distance if distance is not None else 999.0,
                }
                # print( f"[{self.name}] result: {result}, distanza: {distance}, ostacolo: {ostacolo}")
                self.redis_client.update_sensor_data(
                    "brain_memory", {"ostacolo_lidar": ostacolo}
                )

            except Exception as e:
                print(f"[{self.name}] ❌ Errore nel loop: {e}")
            
            time.sleep(self.frequenza_lettura)

    def read_distanza(self):
        """Read the proximity sensor and return detection status and distance.

        Returns:
            tuple[bool | None, float | None]: A tuple containing whether an
            object was detected and its distance in simulator units. If the
            sensor handle is unavailable or a read fails, both values are
            ``None``. When no object is detected, the result is ``(False,
            None)``.
        """
        if not self.handle:
            return None, None

        try:
            res, dist, detectedPoint, detectedObjectHandle, detectedSurfaceNormalVector = self.sim.handleProximitySensor(self.handle)
            if res > 0:
                return True, dist
            else:
                return False, None
        except Exception as e:
            print(f"[{self.name}] Errore di lettura da CoppeliaSim: {e}")
        
        return None, None

            
            

    def stop(self):
        """Stop the background LiDAR-reading thread.

        Returns:
            None. The method waits for the worker thread to finish when it has
            been started.
        """
        self._running = False
        if self._thread:
            self._thread.join()
            print(f"[{self.name}] 🔴 Thread fermato.")