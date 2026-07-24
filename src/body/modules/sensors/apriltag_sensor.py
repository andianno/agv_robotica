from modules.connection.coppelia_connector import CoppeliaConnector
from modules.sensors.generic_sensor import GenericSensor
from modules.connection.redis_interface import RedisInterface 
import threading
import time
import json
import base64
import numpy as np
import cv2
import os
from pupil_apriltags import Detector

SENSORS_KEY = "body_memory"
BRAIN_KEY = "brain_memory"

class AprilTagSensor(GenericSensor):
    def __init__(self, name, clock):
        """Initialize an AprilTag detector synchronized with the simulation.

        Args:
            name: CoppeliaSim vision-sensor object name.
            clock: :class:`SimClock` instance used to schedule reads and
                coordinate barrier acknowledgments.

        Returns:
            None.

        Raises:
            ConnectionError: If Redis is unavailable during initialization.
            OSError: If the node mapping file cannot be read.
        """
        # Richiama il costruttore della classe base (GenericSensor)
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
        
        self.last_data = {"detected": False, "distance": 999.0}

        # Sincronizzazione sul SimClock invece che su un timer reale: è un
        # partecipante GATING della barriera. Il main loop non avanza allo
        # step successivo finché questo sensore non ha completato read() e
        # confermato con ack() — così il contenuto letto corrisponde
        # garantito al tick per cui era stato richiesto, non a "qualunque
        # stato la fisica abbia raggiunto nel frattempo".
        self.clock = clock
        self.physical_dt = self.sim.getSimulationTimeStep()
        target_period_seconds = 0.1  # stesso target di prima (~10Hz)
        self.STEPS_PER_READ = max(1, round(target_period_seconds / self.physical_dt))

        self._running = False
        self._thread = None

        self.BRAIN_KEY = "brain_memory"
        
        # Carica il mapping dei nodi dal JSON (tag_id <-> node_name)
        node_map_path = os.path.join(os.path.dirname(__file__), "../../docs/node_map_id.json")
        try:
            with open(node_map_path) as f:
                self.node_map = json.load(f)  # {node_name: node_id}
            # Crea mapping inverso (tag_id -> node_name)
            self.tag_id_to_node = {v: k for k, v in self.node_map.items()}
            print(f"[{self.name}] Mapping dei nodi caricato: {len(self.tag_id_to_node)} nodi")
        except Exception as e:
            print(f"[{self.name}] Errore nel caricamento della mappa dei nodi: {e}")
            self.tag_id_to_node = {}
        
        # Inizializza il detector AprilTag UNA SOLA VOLTA (molto pesante, non ricrearlo ad ogni frame!)
        self.at_detector = Detector(families='tag36h11', nthreads=1)

    def start(self):
        """Start the clock-synchronized AprilTag-reading thread.

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
        """Read AprilTags at scheduled steps and acknowledge each reading.

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
            self.clock.ack(self.name)
            next_step = actual + self.STEPS_PER_READ

    def read(self):
        """Detect AprilTags in the current vision-sensor image.

        The image is converted to a NumPy array, mirrored, converted to
        grayscale, and processed by the pre-initialized AprilTag detector.
        Recognized tags update the current node and node-presence state in
        Brain memory.

        Returns:
            None. Detection results are written to Redis rather than returned.
        """
        
        if self.handle is None:
            print(f"[{self.name}] Errore: handle del sensore non valido.")
            return
        
        try:
            # 1. Legge l'immagine dal sensore (ZMQ Remote API)
            img_buffer, resolution = self.sim.getVisionSensorImg(self.handle)
            
            if img_buffer is None:
                print(f"[{self.name}] Nessun dato immagine ricevuto.")
                return
            
            # 2. Converte il binario direttamente in un array NumPy (Senza passare per file)
            # Coppia (height, width, 3) per RGB
            img_array = np.frombuffer(img_buffer, dtype=np.uint8).reshape(
                resolution[1], resolution[0], 3
            )
            
            # 3. Pre-elaborazione necessaria (Mirroring e Conversione in scala di grigi)
            img_array = cv2.flip(img_array, 1)
            img_gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

            # 4. Rilevamento (passiamo direttamente l'array 'img_gray')
            # Usa il detector pre-inizializzato nel __init__ (evita creazione ripetuta pesante!)
            tags = self.at_detector.detect(img_gray)

            # 5. Output dei risultati
            if tags:
                for tag in tags:
                    tag_id = tag.tag_id
                    node_name = self.tag_id_to_node.get(tag_id)
                    
                    if node_name:
                        # Aggiorna Redis con sia stato che nodo corrente
                        self.redis_client.update_sensor_data(self.BRAIN_KEY, {
                            "am_i_in_a_node": True,
                            "current_position": node_name
                        })
                        #print(f"[AprilTag] step={self.clock.current_step} tag_id={tag_id} nodo={node_name}")
                        #print(f"[{self.name}] Rilevato AprilTag ID: {tag_id} (Nodo: {node_name})")
                    #else:
                        #print(f"[{self.name}] Tag ID {tag_id} non trovato nella mappa")
            else:
                self.redis_client.update_sensor_data(self.BRAIN_KEY, {
                    "am_i_in_a_node": False
                })
                #print(f"[{self.name}] Nessun AprilTag rilevato.")
                
        except Exception as e:
            print(f"[{self.name}] Errore durante il rilevamento: {e}")


    def stop(self):
        """Stop the AprilTag-reading thread and unregister the clock participant.

        Returns:
            None. The method waits for the worker thread to finish when it has
            been started.
        """
        self._running = False
        self.clock.unregister(self.name)
        if self._thread:
            self._thread.join()
            print(f"[{self.name}] Thread fermato.")