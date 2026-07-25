import time
import py_trees
from py_trees.common import Status

# =============================================================================
# 1. NODI DI SICUREZZA
# =============================================================================

class ControllaOstacolo(py_trees.behaviour.Behaviour):
    """
    Controlla se c'è un allarme ostacolo dal Body (inviato dal sensore Lidar).
    Se insieme all'ostacolo è presente una persona (YOLO), esegue un alert audio.
    """
    def __init__(self):
        super(ControllaOstacolo, self).__init__(name="Ostacolo Rilevato")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        
        # Leggiamo da Redis
        self.blackboard.register_key(key="person_detected", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="ostacolo_lidar", access=py_trees.common.Access.READ)
    
    def setup(self):
        print("Setup ControllaOstacolo")
        return True

    def initialise(self):
        pass

    def update(self):
        # Estrazione sicura (di default falso)
        person_detected = getattr(self.blackboard, "person_detected", False)
        ostacolo_rilevato = getattr(self.blackboard, "ostacolo_lidar", False)

        if ostacolo_rilevato or person_detected:
            if person_detected:
                print("🔊 [SPEAKER] Attenzione: passaggio bloccato, per favore spostarsi.")
            else:
                print("🛑 [LIDAR] Ostacolo non umano rilevato. Macchina bloccata.")
            
            # Attiva la catena di emergenza (StopMotori -> Aspetta)
            return Status.SUCCESS

        # Strada libera
        return Status.FAILURE

class StopMotori(py_trees.behaviour.Behaviour):
    """
    Invia il comando di arresto immediato ai motori.
    """
    def __init__(self):
        super(StopMotori, self).__init__(name="Stop Motori")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)
        
    def setup(self):
        print("Setup StopMotori")
        return True

    def initialise(self):
       pass

    def update(self):       
        LogicController = self.blackboard.logic_controller
        esito = LogicController.execute_stop()
        if esito:
            return Status.SUCCESS
        else:
            return Status.FAILURE



class Aspetta(py_trees.behaviour.Behaviour):
    """
    Esegue un'attesa (es. 5 secondi) prima di riprendere.
    """
    def __init__(self):
        super(Aspetta, self).__init__(name="Aspetta")
        self.duration = 5.0 # Durata dell'attesa in secondi
        self.start_time = None
        
    def setup(self):
        print("Setup Aspetta")
        return True

    def initialise(self):
        self.start_time = time.time()
        print("[StopMotori] Inizio Stop. Attesa di sicurezza attivata...") 
        print(f"[StopMotori] Attesa di {self.duration} secondi...")

    def update(self):
        elapsed_time = time.time() - self.start_time
        if elapsed_time >= self.duration:
            print("[StopMotori] Attesa completata. Ripresa operazioni.")
            return Status.SUCCESS
        else:
            return Status.RUNNING 
