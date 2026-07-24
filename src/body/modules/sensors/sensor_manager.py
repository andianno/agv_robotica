import threading
import time
import json
from modules.connection.redis_interface import RedisInterface

class SensorManager:
    """Coordinate periodic processing of sensor state stored in Redis."""

    BODY_KEY = "body_memory"
    BRAIN_KEY = "brain_memory"
    

    def __init__(self):
        """Initialize the sensor manager and its Redis client.

        Returns:
            None.

        Raises:
            ConnectionError: If Redis is not available during initialization.
        """
        self.redis_client = RedisInterface()
        
        if not self.redis_client.db:
            raise ConnectionError("[SensorManager] Impossibile connettersi a Redis.")

        self._running = False
        self._thread = None
        self.frequenza_controllo = 0.1  # 20 Hz (più veloce dei sensori per non perdere dati)
        self.last_in_node = False

    def start(self):
        """Start the background sensor-monitoring thread.

        Returns:
            None. Calling this method while the manager is already running has
            no effect.
        """
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._loop_logica, daemon=True)
            self._thread.start()
            print(f"[SensorManager] Monitoraggio avviato.")

    def _loop_logica(self):
        """Run the periodic background sensor-processing loop.

        Returns:
            None. The loop exits when ``_running`` becomes ``False``.
        """
        while self._running:
            self._elabora_dati_sensori()
            time.sleep(self.frequenza_controllo)

    def _elabora_dati_sensori(self):
        """Read shared sensor state and update derived Brain state.

        The method reads the Brain and Body memory dictionaries from Redis,
        skips processing when Body memory is empty, and updates the battery
        value in Brain memory when data is available.

        Returns:
            None.
        """
        
        # 1. Usa il tuo nuovo metodo per ottenere direttamente il dizionario Python!
        self.last_in_node = self.redis_client.get_sensor_data(self.BRAIN_KEY).get(self.NODE_KEY)
        body_memory = self.redis_client.get_sensor_data(self.BODY_KEY)
        
        # Se il dizionario è vuoto (i sensori non hanno ancora scritto nulla), saltiamo
        if not body_memory:
            return

        self.redis_client.update_sensor_data(self.BRAIN_KEY, {"battery_level": 100 })
        

    def stop(self):
        """Stop the background sensor-monitoring thread.

        Returns:
            None. The method waits for the worker thread to finish when it has
            been started.
        """
        self._running = False
        if self._thread:
            self._thread.join()
            print("[SensorManager] Monitoraggio fermato.")