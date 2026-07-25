import cv2
import time
import signal
import socket
import numpy as np
from ultralytics import YOLO
import os

from redis_interface_vision import RedisInterfaceVision

# Importa ZMQ solo se necessario
try:
    from coppeliasim_zmqremoteapi_client import RemoteAPIClient
    COPPELIA_AVAILABLE = True
except ImportError:
    COPPELIA_AVAILABLE = False

class PersonDetector:
    def __init__(self, sensor_name="/Robot/visionSensor"):
        # 1. Configurazione ambiente
        self.use_webcam = os.getenv("USE_WEBCAM", "false").lower() == "true"
        # Salvato per poter richiamare _init_coppelia() anche in fase di
        # riconnessione (es. dopo un riavvio della simulazione), vedi _get_frame().
        self.sensor_name = sensor_name

        # 2. Connessione Redis (sempre necessaria), tramite l'interfaccia dedicata.
        # Vision scrive esclusivamente il campo "person_detected" dentro
        # "brain_memory" (stessa chiave letta da Brain e Body). Non esiste e
        # non deve esistere una chiave "vision_memory" separata.
        self.redis_vision = RedisInterfaceVision()

        # Tiene traccia dell'ultimo valore effettivamente scritto su Redis,
        # per scrivere solo sui cambi di stato (edge-triggered) invece che
        # ad ogni frame. None = "non ho ancora scritto nulla": forza una
        # prima scrittura certa all'avvio, qualunque sia il primo valore
        # osservato (True o False).
        self.ultimo_stato_scritto = None
        
        self.is_running = True
        signal.signal(signal.SIGINT, self._gestisci_spegnimento)
        signal.signal(signal.SIGTERM, self._gestisci_spegnimento)

        # 3. Setup sorgente video
        if self.use_webcam:
            print("[PERSON DETECTOR] 📷 Modalità WEBCAM attiva.")
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                print("[PERSON DETECTOR] ❌ ERRORE: Impossibile aprire la webcam.")
                exit(1)
        else:
            print("[PERSON DETECTOR] 🤖 Modalità COPPELIA attiva.")
            self._init_coppelia(sensor_name)

        # 4. Caricamento YOLO
        print("[PERSON DETECTOR] 🧠 Caricamento modello YOLOv8n...")
        self.model = YOLO("yolov8n.pt")

    def _init_coppelia(self, sensor_name):
        if not COPPELIA_AVAILABLE:
            raise ImportError("Libreria CoppeliaSim ZMQ non installata!")
            
        print("[PERSON DETECTOR] 🔌 Connessione diretta a CoppeliaSim in corso...")
        
        max_retries = 30
        delay = 1
        connection_timeout = 5
        connected = False
        coppelia_host = os.getenv("COPPELIA_HOST", "host.docker.internal")
        
        for attempt in range(max_retries):
            print(f"[PERSON DETECTOR] Tentativo {attempt + 1}/{max_retries} - Connessione a {coppelia_host}:23000...")
            
            if not self.is_running:
                print("[PERSON DETECTOR] 🛑 Rilevato segnale di spegnimento durante la connessione. Interruzione...")
                return

            # Prova prima con un test TCP sulla porta
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(connection_timeout)
                result = sock.connect_ex((coppelia_host, 23000))
                sock.close()
                if result == 0:
                    print(f"[PERSON DETECTOR] ✅ Porta 23000 raggiungibile. Connessione a CoppeliaSim...")
                    try:
                        self.client = RemoteAPIClient(host=coppelia_host)
                        self.sim = self.client.getObject('sim')
                        self.cam_handle = self.sim.getObject(sensor_name)
                        print(f"[PERSON DETECTOR] ✅ Telecamera '{sensor_name}' agganciata con successo!")
                        connected = True
                        break
                    except Exception as e:
                        print(f"[PERSON DETECTOR] Errore con RemoteAPIClient: {type(e).__name__}: {e}")
                else:
                    print(f"[PERSON DETECTOR] Porta 23000 non raggiungibile (timeout o rifiuto connessione)")
            except Exception as e:
                print(f"[PERSON DETECTOR] Errore nel test TCP: {e}")
            
            if attempt < max_retries - 1:
                print(f"[PERSON DETECTOR] In attesa {delay}s prima del prossimo tentativo...")
                time.sleep(delay)
                delay = min(delay * 1.5, 10)
        
        if not connected:
            print(f"[PERSON DETECTOR] ❌ ERRORE CRITICO: Impossibile connettersi a CoppeliaSim dopo {max_retries} tentativi.")
            exit(1)

    def _get_frame(self):
        if self.use_webcam:
            ret, frame = self.cap.read()
            return frame if ret else None
        else:
            try:
                img_raw, res = self.sim.getVisionSensorImg(self.cam_handle)
                if not img_raw or not res or len(res) < 2 or res[0] <= 0 or res[1] <= 0:
                    return None
                frame = np.frombuffer(img_raw, dtype=np.uint8).reshape(res[1], res[0], 3)
                frame = cv2.flip(frame, 0)
                return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            except Exception as e:
                print(f"[PERSON DETECTOR] 🔄 Simulazione riavviata o errore ZMQ ({e}). Riconnessione...")
                time.sleep(1)
                self._init_coppelia(self.sensor_name)
                return None

    def _aggiorna_stato_persona(self, trovata: bool) -> bool:
        """Scrive su Redis SOLO se lo stato di rilevamento è cambiato
        rispetto all'ultima scrittura andata a buon fine.

        Riduce il numero di scritture su Redis: se la persona era già
        visibile (o già non visibile) al frame precedente, non riscriviamo
        lo stesso valore ad ogni ciclo. Logga qui, in un unico punto, tutti
        e tre gli esiti possibili (invariato / scritto / fallito) per non
        avere messaggi ambigui o contraddittori in run().

        Args:
            trovata: Esito della detection sul frame corrente.

        Returns:
            bool: True se è stata effettivamente eseguita una scrittura su
            Redis andata a buon fine, False in tutti gli altri casi (stato
            invariato, oppure scrittura tentata ma fallita).
        """
        if trovata == self.ultimo_stato_scritto:
            print(f"[PERSON DETECTOR] ⏭️ Stato invariato ({trovata}), scrittura su Redis saltata.")
            return False

        successo = self.redis_vision.write_person_detected(trovata)
        if successo:
            self.ultimo_stato_scritto = trovata
            print(f"[PERSON DETECTOR] ✏️ Stato SCRITTO su Redis (brain_memory.person_detected = {trovata})")
        else:
            # Non aggiorniamo ultimo_stato_scritto: se Redis era
            # temporaneamente non raggiungibile, al prossimo frame
            # ritenteremo la scrittura, anche se trovata resta invariato
            # rispetto a questo frame.
            print(f"[PERSON DETECTOR] ⚠️ Cambio di stato rilevato ({trovata}) ma scrittura FALLITA. Verrà ritentata al prossimo frame.")

        return successo

    def run(self):
        print("[PERSON DETECTOR] 👁️ Inizio main loop...")
        try:
            while self.is_running:
                frame = self._get_frame()
                if frame is None:
                    time.sleep(0.1)
                    continue

                # YOLO Inference
                risultati = self.model(frame, stream=True, verbose=False)
                trovata = False
                
                for r in risultati:
                    # Salva l'immagine con i box disegnati
                    annotated_frame = r.plot()
                    cv2.imwrite("vista_yolo.jpg", annotated_frame)
                    
                    # Controlla se c'è una persona (soglia abbassata per il manichino di Coppelia)
                    for box in r.boxes:
                        if int(box.cls[0]) == 0 and float(box.conf[0]) > 0.25:
                            trovata = True
                
                print(f"[PERSON DETECTOR] Frame processato. person_detected: {trovata}")
                self._aggiorna_stato_persona(trovata)
                
                if trovata:
                    print(f"[PERSON DETECTOR] 🎯 PERSONA RILEVATA!")
                else:
                    print(f"[PERSON DETECTOR] ❌ Nessuna persona rilevata.")
                
                time.sleep(0.1)
        finally:
            if self.use_webcam: self.cap.release()
            print("[PERSON DETECTOR] Nodo spento.")

    def _gestisci_spegnimento(self, signum, frame):
        print("\n[PERSON DETECTOR] 🛑 Ricevuto segnale di spegnimento da Docker (SIGTERM/SIGINT)!")
        self.is_running = False
        # Forza l'uscita immediata da eventuali time.sleep() lunghi
        raise KeyboardInterrupt()

if __name__ == "__main__":
    try:
        nodo = PersonDetector()
        nodo.run()
    except KeyboardInterrupt:
        print("[PERSON DETECTOR] Arresto completato in modo sicuro.")