from modules.sensors.generic_sensor import GenericSensor
from modules.connection.redis_interface import RedisInterface 
import threading
import time
import json

SENSORS_KEY = "body_memory"

class VisionSensor(GenericSensor):
    def __init__(self, name):
        """Initialize the Redis-backed person-detection sensor.

        Args:
            name: Identifier used in logs for this sensor.

        Returns:
            None.

        Raises:
            ConnectionError: If Redis is unavailable during initialization.
        """
        # Richiama il costruttore della classe base (GenericSensor)
        super().__init__(name)
        
        # Connessione a Redis (Condivisa e sicura grazie al Singleton)
        self.redis_client = RedisInterface()
        if not self.redis_client.db:
            print(f"[{self.name}] Redis non raggiungibile.")
            raise ConnectionError("Redis err")
        
        # La distanza è gestita dal sensore LIDAR separato
        self.last_data = {"detected": False}
        self.frequenza_lettura = 0.1# 10 Hz
        self._running = False
        self._thread = None

    def start(self):
        """Start the background person-detection state reader.

        Returns:
            None. Calling this method while the sensor is already running has
            no effect.
        """
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._loop_lettura, daemon=True)
            self._thread.start()
            print(f"[{self.name}] Thread avviato.")

    def _loop_lettura(self):
        """Poll Brain memory and cache the latest person-detection flag.

        Returns:
            None. The loop exits when ``_running`` becomes ``False``.
        """
        while self._running:
            try:
                risposta_str = self.redis_client.db.get("brain_memory")
                if risposta_str:
                    risposta = json.loads(risposta_str)
                    self.last_data["detected"] = risposta.get("person_detected", False)
            except Exception as e:
                print(f"[{self.name}] Errore lettura da Redis: {e}")
                
            time.sleep(self.frequenza_lettura)
    
    def stop(self):
        """Stop the background person-detection reader.

        Returns:
            None. The method waits for the worker thread to finish when it has
            been started.
        """
        self._running = False
        if self._thread:
            self._thread.join()
            print(f"[{self.name}] Thread fermato.")