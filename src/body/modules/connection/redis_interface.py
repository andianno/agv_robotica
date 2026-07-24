import os
import redis
import json
import threading
from pathlib import Path

class RedisInterface:
    """Provide shared access to Redis state and pub/sub channels.

    The class uses a thread-safe singleton so that all Body components share
    the same Redis connection and serialized sensor state.
    """

    _instance = None
    _lock = threading.Lock()  # Protegge la creazione dell'istanza in ambienti multithread
    
    COMMAND_CHANNEL = "agv_command_channel"
    RESET_CHANNEL = "agv_reset"
    
    def __new__(cls):
        """Return the shared :class:`RedisInterface` instance.

        Returns:
            RedisInterface: The process-wide, thread-safe singleton instance.
        """
        # Se l'istanza non esiste, la creiamo in modo thread-safe
        if cls._instance is None:
            with cls._lock:
                # Doppia verifica (double-checked locking)
                if cls._instance is None:
                    cls._instance = super(RedisInterface, cls).__new__(cls)
                    # Flag per assicurarci che __init__ giri una sola volta
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the shared Redis connection once.

        The Redis host is read from the ``REDIS_HOST`` environment variable;
        ``localhost`` is used when the variable is not set. A failed
        connection is reported and leaves ``db`` set to ``None``.

        Returns:
            None.
        """
        # Impedisce la sovrascrittura della connessione se l'istanza esiste già
        if self._initialized:
            return
            
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        self.db = None
        
        try:
            self.db = redis.Redis(host=redis_host, port=6379, decode_responses=True)
            self.db.ping()
            self._initialized = True
            print(f"[{self.__class__.__name__}] Connessione a Redis stabilita con successo.")
        except redis.exceptions.ConnectionError:
            self.db = None
            print(f"[{self.__class__.__name__}] ERRORE: Impossibile connettersi a Redis.")

    def subscribe_to_commands(self):
        """Subscribe to the command and reset channels.

        Returns:
            redis.client.PubSub | None: A Redis pub/sub object subscribed to
            ``agv_command_channel`` and ``agv_reset``, or ``None`` when Redis
            is unavailable.
        """
        if not self.db:
            return None
        pubsub = self.db.pubsub()
        pubsub.subscribe(self.COMMAND_CHANNEL, self.RESET_CHANNEL)
        print(f"[{self.__class__.__name__}] Iscritto ai canali {self.COMMAND_CHANNEL} e {self.RESET_CHANNEL}.")
        return pubsub
        
    def set_sensor_data(self, key: str, data: dict):
        """Serialize and store a complete sensor-state dictionary.

        Args:
            key: Redis key under which the state is stored.
            data: JSON-serializable sensor-state dictionary.

        Returns:
            None. No write is performed when Redis is unavailable.
        """
        if self.db:
            self.db.set(key, json.dumps(data))

    def update_sensor_data(self, key: str, partial_data: dict):
        """Merge partial sensor data into the state stored at a Redis key.

        If the existing value is missing or is not valid JSON, it is treated
        as an empty dictionary before applying the update.

        Args:
            key: Redis key containing the state to update.
            partial_data: JSON-serializable fields to merge into the state.

        Returns:
            None. No update is performed when Redis is unavailable.
        """
        if not self.db:
            return

        existing_data_str = self.db.get(key)
        if existing_data_str:
            try:
                current_data = json.loads(existing_data_str)
            except json.JSONDecodeError:
                current_data = {}
        else:
            current_data = {}

        current_data.update(partial_data)
        self.db.set(key, json.dumps(current_data))

    def get_sensor_data(self, key: str) -> dict:
        """Read a sensor-state dictionary from Redis.

        Args:
            key: Redis key containing the serialized sensor state.

        Returns:
            dict: The decoded state, or an empty dictionary when Redis is
            unavailable or the key does not exist.

        Raises:
            json.JSONDecodeError: If the stored value is not valid JSON.
        """
        if self.db:
            data = self.db.get(key)
            if data:
                return json.loads(data)
        return {}

    def initialize_body_memory(self):
        """Initialize the Body memory with its default state.

        The method loads the node-to-AprilTag mapping from
        ``docs/node_map_id.json`` and stores the default maneuver, PID, and
        node mapping values under the ``body_memory`` Redis key.

        Returns:
            None. No initialization is performed when Redis is unavailable.

        Raises:
            OSError: If the node mapping file cannot be opened.
            json.JSONDecodeError: If the node mapping file is invalid JSON.
        """
        if not self.db:
            print(f"[{self.__class__.__name__}] ❌ Redis non disponibile per l'inizializzazione!")
            return
        
        # Carica il mapping nodo → tag_id dal file JSON
        node_map_path = Path(__file__).resolve().parents[2] / "docs" / "node_map_id.json"
        with open(node_map_path, "r", encoding="utf-8") as f:
            node_map = json.load(f)
            
        initial_state = {
            # "current_position": "ER",
            "maneuver_state": "NONE",  # Può essere "NONE", "IN_PROGRESS", "COMPLETED"
            "pid_active": False,
            "node_id": json.dumps(node_map)     # ID dei nodi per AprilTags
        }
        
        self.set_sensor_data("body_memory", initial_state)
        print(f"[{self.__class__.__name__}] ✅ Body memory inizializzata con stato di default.")

    def initialize_brain_memory(self):
        """Initialize the Brain memory with its default state.

        The default state contains flags for person detection, node presence,
        and whether the vehicle is carrying a load.

        Returns:
            None. No initialization is performed when Redis is unavailable.
        """
        if not self.db:
            print(f"[{self.__class__.__name__}] ❌ Redis non disponibile per l'inizializzazione!")
            return
        
        initial_state = {
            "person_detected": False,  
            "am_i_in_a_node": False,
            "is_load": False
        }
        
        self.set_sensor_data("brain_memory", initial_state)
        print(f"[{self.__class__.__name__}] ✅ Brain memory inizializzata con stato di default.")

    def set_command(self, channel: str, command):
        """Publish a command on a Redis pub/sub channel.

        Dictionary commands are serialized as JSON; all other command values
        are converted to strings before publication.

        Args:
            channel: Redis pub/sub channel that should receive the command.
            command: Dictionary or scalar command payload to publish.

        Returns:
            bool: ``True`` when the command is published, otherwise ``False``
            when Redis is unavailable or publication fails.
        """
        if not self.db:
            print(f"[{self.__class__.__name__}] ❌ Redis non disponibile!")
            return False
        
        try:
            # Se il comando è un dizionario, lo converte in JSON
            if isinstance(command, dict):
                command_json = json.dumps(command)
            else:
                command_json = str(command)
            
            # Pubblica il comando sul canale
            num_subscribers = self.db.publish(channel, command_json)
            print(f"[{self.__class__.__name__}] Comando pubblicato su {channel}: {command_json} (subscribers: {num_subscribers})")
            return True
        except Exception as e:
            print(f"[{self.__class__.__name__}] ❌ Errore nella pubblicazione del comando: {e}")
            return False