import time
import py_trees
from py_trees.common import Status

# =============================================================================
# 3. MISSION MANAGEMENT NODES
# =============================================================================

class ListaPalletVuota(py_trees.behaviour.Behaviour):
    """
    Condition: checks whether the pallet list to process is empty.
    Returns SUCCESS if there is no more work to do.
    """
    def __init__(self):
        """Registers read access to the mission queue and current target on the blackboard."""
        super(ListaPalletVuota, self).__init__(name="Lista Pallet Vuota")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="mission_queue", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="pallet_list_empty", access=py_trees.common.Access.READ) 
        self.blackboard.register_key(key="current_target", access=py_trees.common.Access.READ)

    def setup(self):
        """py_trees lifecycle hook, called once when the tree is set up."""
        print("Setup ListaPalletVuota")
        return True

    def initialise(self):
        """py_trees lifecycle hook, called once each time this node starts running. Nothing to do here."""
        pass

    def update(self):
        """Returns SUCCESS if the whole mission is over (no pallets, no queue, no current target), FAILURE otherwise."""
        try:
            magazzino_vuoto = self.blackboard.pallet_list_empty
            coda_locale = self.blackboard.mission_queue
            target_attuale = self.blackboard.current_target
        except KeyError:
            return py_trees.common.Status.FAILURE
        
        if magazzino_vuoto and not coda_locale and target_attuale is None:
            print("[ListaPalletVuota] Missione globale conclusa. Rientro alla base.")
            return py_trees.common.Status.SUCCESS
        
        return py_trees.common.Status.FAILURE

class PianoNonGenerato(py_trees.behaviour.Behaviour):
    """
    Condition: checks whether a navigation plan for the current pallets is missing.
    Returns SUCCESS if a new plan needs to be generated.
    """
    def __init__(self):
        """Registers read access to the current target and mission queue on the blackboard."""
        super(PianoNonGenerato, self).__init__(name="Piano Non Generato")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="current_target", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="mission_queue", access=py_trees.common.Access.READ)

    def setup(self):
        """py_trees lifecycle hook, called once when the tree is set up."""
        print("Setup PianoNonGenerato")
        return True

    def initialise(self):
        """py_trees lifecycle hook, called once each time this node starts running. Nothing to do here."""
        pass

    def update(self):
        """Returns SUCCESS if there is no current target and the mission queue is empty (a new plan is needed)."""
        try:
            target_attuale = self.blackboard.current_target
            coda_locale = self.blackboard.mission_queue
        except KeyError:
            return py_trees.common.Status.FAILURE
        
        if target_attuale is None and len(coda_locale) == 0:
            print("[PianoNonGenerato] Nuova missione da pianificare.")
            return py_trees.common.Status.SUCCESS
        
        return py_trees.common.Status.FAILURE
        
class RiceviListaPallet(py_trees.behaviour.Behaviour):
    """
    Action:  download new tasks.
    If there are no tasks or the server is unreachable, puts the tree in an idle wait state.
    """
    def __init__(self):
        """Registers read access to the shared logic_controller on the blackboard."""
        super(RiceviListaPallet, self).__init__(name="Ricevi Lista Pallet")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)

    def setup(self):
        """py_trees lifecycle hook, called once when the tree is set up."""
        print("Setup RiceviListaPallet")
        return True

    def initialise(self):
        """py_trees lifecycle hook, called once each time this node starts running. Nothing to do here."""
        pass

    def update(self):
        """Downloads the mission from the central system and returns SUCCESS/FAILURE accordingly."""
        try:
            lc = self.blackboard.logic_controller
        except KeyError:
            return py_trees.common.Status.FAILURE

        esito = lc.download_mission_from_central_system()
        if esito == "FAILURE":
            print(f"[{self.name}] ERRORE: Impossibile scaricare la lista pallet.")
            return py_trees.common.Status.FAILURE
        else:
            print(f"[{self.name}] Lista pallet scaricata con successo: {esito}")
            return py_trees.common.Status.SUCCESS
            
class GeneraPianoOttimale(py_trees.behaviour.Behaviour):
    """
    Action: computes the optimal mission ordering (task scheduling) using a balanced Greedy algorithm.
    """
    def __init__(self):
        """Registers read access to the shared logic_controller on the blackboard."""
        super(GeneraPianoOttimale, self).__init__(name="Genera Piano Ottimale")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)

    def update(self):
        """Builds the optimal mission plan and returns SUCCESS/FAILURE accordingly."""

        lc = self.blackboard.logic_controller
        esito = lc.create_optimal_plan()
        if esito == "FAILURE":
            print(f"[{self.name}] ERRORE: Impossibile generare un piano ottimale.")
            return py_trees.common.Status.FAILURE
        else:            
            print(f"[{self.name}] Piano ottimale generato con successo: {esito}")
            return py_trees.common.Status.SUCCESS
            
class NavigaVersoTarget(py_trees.behaviour.Behaviour):
    """
    Action: drives the AGV towards the current mission target, one BT tick at a time.
    """
    def __init__(self):
        """Registers read access to the shared logic_controller on the blackboard."""
        super(NavigaVersoTarget, self).__init__(name="Naviga Verso Target")
        print("Inizializzo nodo NavigaVersoTarget")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)

    def setup(self):
        """py_trees lifecycle hook, called once when the tree is set up."""
        print("Setup NavigaVersoTarget")
        return True

    def initialise(self):
        """py_trees lifecycle hook, called once each time this node starts running. Nothing to do here."""
        pass

    def update(self):
        """Advances navigation towards the current target and returns SUCCESS/RUNNING/FAILURE accordingly."""
        esito = self.blackboard.logic_controller.navigate_to_current_target()
        if esito == "SUCCESS":
            return py_trees.common.Status.SUCCESS
        elif esito == "RUNNING":
            return py_trees.common.Status.RUNNING
        else:
                return py_trees.common.Status.FAILURE
        
class IlPercorsoEStatoCalcolato(py_trees.behaviour.Behaviour):
    """
    Condition: checks whether a valid path to the current target has already been computed.
    """
    def __init__(self):
        """Registers read access to the path and current target on the blackboard."""
        print("Inizializzo nodo IlPercorsoEStatoCalcolato")
        super(IlPercorsoEStatoCalcolato, self).__init__(name="Il Percorso È Stato Calcolato")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="path_to_target", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="current_target", access=py_trees.common.Access.READ)

    def setup(self):
        """py_trees lifecycle hook, called once when the tree is set up."""
        print("Setup IlPercorsoEStatoCalcolato")
        return True

    def initialise(self):
        """py_trees lifecycle hook, called once each time this node starts running. Nothing to do here."""
        pass

    def update(self):
        """Returns SUCCESS if a non-empty path to the current target exists, FAILURE otherwise."""
        try:
            percorso = self.blackboard.path_to_target
            target_attuale = self.blackboard.current_target
        except KeyError:
            return py_trees.common.Status.FAILURE
        
        # Check if there is a valid path to the current target
        if target_attuale is not None and isinstance(percorso, list) and len(percorso) > 0:
            print(f"[{self.name}] Il percorso verso il target {target_attuale} è stato calcolato.")
            return py_trees.common.Status.SUCCESS

        # If there is no path, it means either there was an error or
        # we have reached the target, performed a pickup/dropoff, 
        # and now need to decide the next target to reach.
        return py_trees.common.Status.FAILURE
    
class CalcolaPercorso(py_trees.behaviour.Behaviour):
    """
    Action: computes the path from the current position to the current mission target.
    """
    def __init__(self):
        """Registers read access to the shared logic_controller on the blackboard."""
        print("Inizializzo nodo CalcolaPercorso")
        super(CalcolaPercorso, self).__init__(name="Calcola Percorso")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)

    def setup(self):
        """py_trees lifecycle hook, called once when the tree is set up."""
        print("Setup CalcolaPercorso")
        return True

    def initialise(self):
        """py_trees lifecycle hook, called once each time this node starts running. Nothing to do here."""
        pass

    def update(self):
        """Computes the path to the current target and returns SUCCESS/FAILURE accordingly."""
        try:
            lc = self.blackboard.logic_controller
        except KeyError:
            return py_trees.common.Status.FAILURE

        esito = lc.calculate_path_to_current_target()
        if esito == "FAILURE":
            print(f"[{self.name}] ERRORE: Impossibile calcolare il percorso verso il target.")
            return py_trees.common.Status.FAILURE
        else:
            print(f"[{self.name}] Percorso calcolato con successo: {esito}")
            return py_trees.common.Status.SUCCESS