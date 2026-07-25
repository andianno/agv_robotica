# FILE: src/vision/redis_interface_vision.py

import os
import redis
import json


class RedisInterfaceVision:
    """Gestisce tutto ciò che riguarda Redis per il container Vision.

    Il container Vision ha un solo compito su Redis: comunicare al resto del
    sistema se in questo momento vede una persona. Questa classe è l'UNICO
    punto di accesso a Redis per Vision — connessione, lettura, scrittura —
    e per disegno espone un solo metodo di scrittura pubblico,
    `write_person_detected()`, che aggiorna esclusivamente il campo
    "person_detected" dentro "brain_memory" (la stessa chiave letta da Brain
    in logic_controller.py e da Body in vision_sensor.py).

    Non esiste un metodo generico per scrivere una chiave/campo qualsiasi:
    è una scelta voluta, non solo una convenzione. Anche cambiando
    person_detector.py in futuro, non è possibile passare da questa classe
    a scrivere o cancellare altri campi (battery_level, current_position,
    is_load, ecc.) su "brain_memory" — Vision può solo raccontare quello che
    vede, non toccare il resto dello stato condiviso.
    """

    BRAIN_MEMORY_KEY = "brain_memory"
    PERSON_DETECTED_FIELD = "person_detected"

    def __init__(self):
        """Stabilisce la connessione a Redis.

        L'host viene letto dalla variabile d'ambiente REDIS_HOST (default
        "localhost"). Se la connessione fallisce, self.db resta None e ogni
        scrittura successiva viene ignorata in modo sicuro, senza propagare
        eccezioni al chiamante (person_detector.py continua a girare anche
        se Redis non è ancora pronto).

        Returns:
            None.
        """
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        self.db = None

        try:
            self.db = redis.Redis(host=redis_host, port=6379, decode_responses=True)
            self.db.ping()
            print(f"[{self.__class__.__name__}] Connessione a Redis stabilita con successo ({redis_host}).")
        except redis.exceptions.ConnectionError:
            self.db = None
            print(f"[{self.__class__.__name__}] ERRORE: Impossibile connettersi a Redis ({redis_host}).")

    @property
    def is_connected(self) -> bool:
        """True se la connessione a Redis è attiva.

        Returns:
            bool: Stato della connessione.
        """
        return self.db is not None

    def write_person_detected(self, detected: bool) -> bool:
        """Scrive ESCLUSIVAMENTE il campo "person_detected" su "brain_memory".

        Esegue un read-modify-write: legge lo stato attuale salvato sotto
        "brain_memory", aggiorna solo la chiave "person_detected" e riscrive
        il dizionario risultante, lasciando intatti tutti gli altri campi già
        presenti (scritti da Brain o da Body). Non è un semplice SET che
        sovrascrive l'intera chiave: se lo fosse, ogni chiamata da Vision
        cancellerebbe tutto lo stato scritto dagli altri componenti.

        Args:
            detected: True se YOLO ha rilevato una persona nel frame corrente,
                False altrimenti.

        Returns:
            bool: True se la scrittura è andata a buon fine, False se Redis
            non è raggiungibile o la scrittura è fallita per qualunque motivo.
        """
        return self._merge_write(self.BRAIN_MEMORY_KEY, {self.PERSON_DETECTED_FIELD: bool(detected)})

    def _merge_write(self, key: str, partial_data: dict) -> bool:
        """Aggiorna SOLO i campi presenti in `partial_data`, senza toccare il resto.

        Metodo privato (uso interno): implementa il read-modify-write generico
        usato da `write_person_detected`. Non è esposto pubblicamente — questo
        è deliberato: impedisce che il container Vision possa scrivere campi
        arbitrari su Redis, anche per errore o per un futuro refactor
        distratto di person_detector.py.

        Args:
            key: Chiave Redis da aggiornare.
            partial_data: Campi da unire allo stato già esistente sotto `key`.

        Returns:
            bool: True se la scrittura è andata a buon fine, False altrimenti
            (Redis non disponibile, o errore durante lettura/scrittura).
        """
        if not self.db:
            print(f"[{self.__class__.__name__}] ❌ Redis non disponibile, scrittura ignorata.")
            return False

        try:
            existing_data_str = self.db.get(key)
            if existing_data_str:
                try:
                    current_data = json.loads(existing_data_str)
                    if not isinstance(current_data, dict):
                        current_data = {}
                except json.JSONDecodeError:
                    # Dato corrotto su Redis: ripartiamo da un dizionario vuoto
                    # invece di propagare l'errore, così non blocchiamo il loop
                    # di detection per un problema di un altro componente.
                    current_data = {}
            else:
                current_data = {}

            current_data.update(partial_data)
            self.db.set(key, json.dumps(current_data))
            return True
        except Exception as e:
            print(f"[{self.__class__.__name__}] ❌ Errore durante la scrittura su Redis: {e}")
            return False