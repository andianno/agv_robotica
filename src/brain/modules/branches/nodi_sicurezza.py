import time
import py_trees
from py_trees.common import Status

# =============================================================================
# 1. SEAFETY NODES FOR OBSTACLE DETECTION AND EMERGENCY STOP
# =============================================================================

class ControllaOstacolo(py_trees.behaviour.Behaviour):
    """
    Checks whether the Body raised an obstacle alarm (sent by the Lidar sensor).
    If a person is also detected (YOLO), triggers an audio alert.
    """
    def __init__(self):
        """Registers read access to the obstacle/person-detection flags on the blackboard."""
        super(ControllaOstacolo, self).__init__(name="Ostacolo Rilevato")
        self.blackboard = py_trees.blackboard.Client(name=self.name)

        # Leggiamo da Redis
        self.blackboard.register_key(key="person_detected", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="ostacolo_lidar", access=py_trees.common.Access.READ)

    def setup(self):
        """py_trees lifecycle hook, called once when the tree is set up."""
        print("Setup ControllaOstacolo")
        return True

    def initialise(self):
        """py_trees lifecycle hook, called once each time this node starts running. Nothing to do here."""
        pass

    def update(self):
        """Returns SUCCESS (triggering the safety stop) if an obstacle or a person is detected, FAILURE otherwise."""
        person_detected = getattr(self.blackboard, "person_detected", False)
        ostacolo_rilevato = getattr(self.blackboard, "ostacolo_lidar", False)

        if ostacolo_rilevato or person_detected:
            if person_detected:
                print("🔊 [SPEAKER] Attenzione: passaggio bloccato, per favore spostarsi.")
            else:
                print("🛑 [LIDAR] Ostacolo non umano rilevato. Macchina bloccata.")
            
            # Activates the emergency chain (StopMotori -> Aspetta)
            return Status.SUCCESS

        # free way, no obstacle detected
        return Status.FAILURE

class StopMotori(py_trees.behaviour.Behaviour):
    """
    Sends the immediate motor stop command.
    """
    def __init__(self):
        """Registers read access to the shared logic_controller on the blackboard."""
        super(StopMotori, self).__init__(name="Stop Motori")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)

    def setup(self):
        """py_trees lifecycle hook, called once when the tree is set up."""
        print("Setup StopMotori")
        return True

    def initialise(self):
       """py_trees lifecycle hook, called once each time this node starts running. Nothing to do here."""
       pass

    def update(self):
        """Executes the stop command and returns SUCCESS/FAILURE based on the outcome."""
        LogicController = self.blackboard.logic_controller
        esito = LogicController.execute_stop()
        if esito:
            return Status.SUCCESS
        else:
            return Status.FAILURE

class Aspetta(py_trees.behaviour.Behaviour):
    """
    Waits for a fixed duration (e.g. 5 seconds) before resuming.
    """
    def __init__(self):
        """Sets up the fixed wait duration (in seconds) before this node reports SUCCESS."""
        super(Aspetta, self).__init__(name="Aspetta")
        self.duration = 5.0 # Seconds to wait before resuming
        self.start_time = None

    def setup(self):
        """py_trees lifecycle hook, called once when the tree is set up."""
        print("Setup Aspetta")
        return True

    def initialise(self):
        """Starts the wait timer each time this node begins running."""
        self.start_time = time.time()
        print("[StopMotori] Inizio Stop. Attesa di sicurezza attivata...")
        print(f"[StopMotori] Attesa di {self.duration} secondi...")

    def update(self):
        """Returns SUCCESS once the wait duration has elapsed, RUNNING otherwise."""
        elapsed_time = time.time() - self.start_time
        if elapsed_time >= self.duration:
            print("[StopMotori] Attesa completata. Ripresa operazioni.")
            return Status.SUCCESS
        else:
            return Status.RUNNING 
