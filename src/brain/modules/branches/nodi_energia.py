import time
import py_trees
from py_trees.common import Status

# =============================================================================
# 2. ENERGY MANAGEMENT NODES
# =============================================================================

class ControlloBatteria(py_trees.behaviour.Behaviour):
    """
    Checks the battery level.
    Returns SUCCESS if the battery is CRITICAL (< 20%), triggering the recharge sequence.
    """
    def __init__(self):
        """Registers read access to battery_level/is_charging and the shared logic_controller on the blackboard."""
        super(ControlloBatteria, self).__init__(name="Controllo Batteria < 20%")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="battery_level", access=py_trees.common.Access.READ)

        #this flag is used to indicate that we are below 20% and need to recharge,
        #this is to avoid re-entering this condition at every tick of the BT
        #it will be set to True when the battery drops below 20% and to False when the recharge is complete
        self.blackboard.register_key(key="is_charging", access=py_trees.common.Access.READ)

    def setup(self):
        """py_trees lifecycle hook, called once when the tree is set up."""
        print("Setup ControlloBatteria")
        return True

    def initialise(self):
        """py_trees lifecycle hook, called once each time this node starts running. Nothing to do here."""
        pass

    def update(self):
        """Toggles charge mode based on battery level and returns SUCCESS while charging is active, FAILURE otherwise."""
        livello_batteria = self.blackboard.battery_level
        # If the battery is below 20%, activate "Charge Mode"
        if livello_batteria < 20:
            self.blackboard.logic_controller.set_energy_mode("CHARGE_MODE")
        if livello_batteria >= 100.0:
            self.blackboard.logic_controller.set_energy_mode("NORMAL_MODE")

        # Return SUCCESS if we are in charge mode, otherwise FAILURE
        if self.blackboard.is_charging:
            if livello_batteria < 20:
                print(f"[ControlloBatteria] Batteria critica: {livello_batteria}%. Attivo modalità ricarica.")
            return Status.SUCCESS
        else:
            return Status.FAILURE

class CalcolaPercorsoRicarica(py_trees.behaviour.Behaviour):
    """
    Computes the optimal path to the nearest recharge station.
    """
    def __init__(self, nodo_ricarica="ER"):
        """Stores the recharge station node and registers the blackboard keys needed to read the current position and write the path."""
        super(CalcolaPercorsoRicarica, self).__init__(name="Calcola Percorso Ricarica")
        self.nodo_ricarica = nodo_ricarica

        # Blackboard client for reading the current position and writing the path to follow
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="current_position", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="path_to_target", access=py_trees.common.Access.READ)

    def setup(self):
        """py_trees lifecycle hook, called once when the tree is set up."""
        print("Setup CalcolaPercorsoRicarica")
        return True

    def initialise(self):
        """py_trees lifecycle hook, called once each time this node starts running. Nothing to do here."""
        pass

    def update(self):
        """Computes (or reuses) the path to the recharge station and returns SUCCESS/FAILURE accordingly."""
        LogicController = self.blackboard.logic_controller
        # read the current position from the blackboard
        try:
            nodo_partenza = self.blackboard.current_position
        except KeyError:
            print("[CalcolaPercorsoRicarica] Errore: Posizione 'current_position' non trovata sulla blackboard.")
            return Status.FAILURE
        # If we are already on the way to the recharge station, don't recalculate the path
        if self.blackboard.path_to_target and self.blackboard.path_to_target[-1] == self.nodo_ricarica:
            print("[CalcolaPercorsoRicarica] Già in missione verso la stazione di ricarica, non ricalcolo il percorso.")
            return Status.SUCCESS
        else:
            esito = LogicController.find_path_to_recharge(nodo_partenza, self.nodo_ricarica)
            match esito:
                case True:
                    return Status.SUCCESS
                case False:
                    return Status.FAILURE

class VaiAStazioneRicarica(py_trees.behaviour.Behaviour):
    """
    Handles physical navigation towards the recharge station.
    """
    def __init__(self):
        """Registers read access to the path and the shared logic_controller on the blackboard."""
        super(VaiAStazioneRicarica, self).__init__(name="Vai A Stazione Ricarica")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="path_to_target", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)

    def setup(self):
        """py_trees lifecycle hook, called once when the tree is set up."""
        print("Setup VaiAStazioneRicarica")
        return True

    def initialise(self):
        """py_trees lifecycle hook, called once each time this node starts running. Nothing to do here."""
        pass

    def update(self):
        """Drives towards the recharge station, mapping the logic controller outcome to a py_trees Status."""
        LogicController = self.blackboard.logic_controller
        esito = LogicController.go_to_charge_station()
        match esito:
            case "SUCCESS":
                return Status.SUCCESS
            case "FAILURE":
                return Status.FAILURE
            case "RUNNING":
                return Status.RUNNING
            
class RicaricaBatteria(py_trees.behaviour.Behaviour):
    """
    Handles the recharge process (waits until the battery reaches 100%).
    """
    def __init__(self):
        """Registers read access to battery_level and the shared logic_controller on the blackboard."""
        super(RicaricaBatteria, self).__init__(name="Ricarica Batteria")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="battery_level", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)

    def setup(self):
        """py_trees lifecycle hook, called once when the tree is set up."""
        print("Setup RicaricaBatteria")
        return True

    def initialise(self):
        """py_trees lifecycle hook, called once each time this node starts running."""
        print("[RicaricaBatteria] Inizio ricarica... Attesa fino al 100%")

    def update(self):
        """Advances the recharge process and returns SUCCESS/RUNNING/FAILURE based on the outcome."""
        try:
            logic_controller = self.blackboard.logic_controller
        except KeyError:
            print("[RicaricaBatteria] Errore: 'logic_controller' non trovato sulla blackboard.")
            return Status.FAILURE
        
        esito = logic_controller.recharge_battery()

        match esito:
            case "SUCCESS":
                print(f"[RicaricaBatteria] Ricarica completata: {self.blackboard.battery_level}%.")
                return Status.SUCCESS
            case "RUNNING":
                print(f"[RicaricaBatteria] In ricarica... livello attuale: {self.blackboard.battery_level}%")
                return Status.RUNNING
            case "FAILURE":
                print("[RicaricaBatteria] Errore durante la ricarica.")
                return Status.FAILURE