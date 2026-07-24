import cv2
import time
import signal
import numpy as np
from ultralytics import YOLO
import redis
import json
import os

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
        indirizzo_redis = os.getenv("REDIS_HOST", "host.docker.internal")
        
        # 2. Connessione Redis (sempre necessaria)
        self.r = redis.Redis(host=indirizzo_redis, port=6379, db=0, decode_responses=True)
        self.chiave_scrittura = "body_memory"
        
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
        
        self.is_running = True
        signal.signal(signal.SIGINT, self._gestisci_spegnimento)
        signal.signal(signal.SIGTERM, self._gestisci_spegnimento)

    def _init_coppelia(self, sensor_name):
        if not COPPELIA_AVAILABLE:
            raise ImportError("Libreria CoppeliaSim ZMQ non installata!")
        # Connessione con retry (simile al tuo vecchio codice)
        self.client = RemoteAPIClient(host=os.getenv("COPPELIA_HOST", "host.docker.internal"))
        self.sim = self.client.getObject('sim')
        self.cam_handle = self.sim.getObject(sensor_name)

    def _get_frame(self):
        """Metodo astratto per ottenere il frame dalla sorgente scelta."""
        if self.use_webcam:
            ret, frame = self.cap.read()
            return frame if ret else None
        else:
            img_raw, res = self.sim.getVisionSensorImg(self.cam_handle)
            if not img_raw: return None
            frame = np.frombuffer(img_raw, dtype=np.uint8).reshape(res[1], res[0], 3)
            frame = cv2.flip(frame, 0)
            return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    def _update_brain_memory(self, partial_data):
        try:
            # Recupera stato attuale e aggiorna solo i campi necessari
            data_str = self.r.get(self.chiave_scrittura)
            current_data = json.loads(data_str) if data_str else {}
            if not isinstance(current_data, dict): current_data = {}
            
            current_data.update(partial_data)
            self.r.set(self.chiave_scrittura, json.dumps(current_data))
        except Exception as e:
            print(f"[PERSON DETECTOR] Errore Redis: {e}")

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
                trovata = any(int(box.cls[0]) == 0 and float(box.conf[0]) > 0.50 
                              for r in risultati for box in r.boxes)
                
                print(f"[PERSON DETECTOR] Frame processato. person_detected: {trovata}")
                self._update_brain_memory({"person_detected": trovata})
                print(f"[PERSON DETECTOR] Stato aggiornato su body_memory: person_detected = {trovata}")
                
                if trovata:
                    print(f"[PERSON DETECTOR] 🎯 PERSONA RILEVATA!")
                if not trovata:
                    print(f"[PERSON DETECTOR] ❌ Nessuna persona rilevata.")
                
                time.sleep(0.1)
        finally:
            if self.use_webcam: self.cap.release()
            print("[PERSON DETECTOR] Nodo spento.")

    def _gestisci_spegnimento(self, signum, frame):
        self.is_running = False

if __name__ == "__main__":
    nodo = PersonDetector()
    nodo.run()