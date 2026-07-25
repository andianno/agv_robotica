import time
import py_trees
from py_trees.common import Status

# =============================================================================
# 3. NODI DI GESTIONE MISSIONE
# =============================================================================

class ListaPalletVuota(py_trees.behaviour.Behaviour):
    """
    Condizione: Verifica se la lista dei pallet da processare è vuota.
    Restituisce SUCCESS se non ci sono più lavori da fare.
    """
    def __init__(self):
        super(ListaPalletVuota, self).__init__(name="Lista Pallet Vuota")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="mission_queue", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="pallet_list_empty", access=py_trees.common.Access.READ) 
        self.blackboard.register_key(key="current_target", access=py_trees.common.Access.READ)
    
    def setup(self):
        print("Setup ListaPalletVuota")
        return True

    def initialise(self):
        pass

    def update(self):
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
    Condizione: Verifica se manca un piano di navigazione per i pallet attuali.
    Restituisce SUCCESS se bisogna generare un nuovo piano.
    """
    def __init__(self):
        super(PianoNonGenerato, self).__init__(name="Piano Non Generato")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="current_target", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="mission_queue", access=py_trees.common.Access.READ)

    
    def setup(self):
        print("Setup PianoNonGenerato")
        return True

    def initialise(self):
        pass

    def update(self):
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
    Azione: Contatta il Fleet Manager tramite API REST per scaricare i nuovi task.
    Se non ci sono task o il server è irraggiungibile, mette l'albero in attesa (IDLE).
    """
    def __init__(self):
        super(RiceviListaPallet, self).__init__(name="Ricevi Lista Pallet")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)

    def setup(self):
        print("Setup RiceviListaPallet")
        return True

    def initialise(self):
        pass

    def update(self):
        try:
            lc = self.blackboard.logic_controller
        except KeyError:
            return py_trees.common.Status.FAILURE

        esito = lc.download_mission_from_central_system()
        if esito == "FAILURE":
            print(f"[{self.name}] ERRORE: Impossibile contattare il Fleet Manager per scaricare la lista pallet.")
            return py_trees.common.Status.FAILURE
        else:
            print(f"[{self.name}] Lista pallet scaricata con successo: {esito}")
            return py_trees.common.Status.SUCCESS
            

class GeneraPianoOttimale(py_trees.behaviour.Behaviour):
    """
    Azione: Elabora l'ordine ottimale delle missioni (task scheduling) con algortmo Greedy (per zio Daniele) bilanciato.
    """
    def __init__(self):
        super(GeneraPianoOttimale, self).__init__(name="Genera Piano Ottimale")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)

    def update(self):

        lc = self.blackboard.logic_controller
        esito = lc.create_optimal_plan()
        if esito == "FAILURE":
            print(f"[{self.name}] ERRORE: Impossibile generare un piano ottimale.")
            return py_trees.common.Status.FAILURE
        else:            
            print(f"[{self.name}] Piano ottimale generato con successo: {esito}")
            return py_trees.common.Status.SUCCESS
            

class NavigaVersoTarget(py_trees.behaviour.Behaviour):
    def __init__(self):
        super(NavigaVersoTarget, self).__init__(name="Naviga Verso Target")
        print("Inizializzo nodo NavigaVersoTarget")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)

    def setup(self):
        print("Setup NavigaVersoTarget")
        return True

    def initialise(self):
        pass

    def update(self):
        esito = self.blackboard.logic_controller.navigate_to_current_target()
        if esito == "SUCCESS":
            return py_trees.common.Status.SUCCESS
        elif esito == "RUNNING":
            return py_trees.common.Status.RUNNING
        else:
                return py_trees.common.Status.FAILURE
        
class IlPercorsoEStatoCalcolato(py_trees.behaviour.Behaviour):
    def __init__(self):
        print("Inizializzo nodo IlPercorsoEStatoCalcolato")
        super(IlPercorsoEStatoCalcolato, self).__init__(name="Il Percorso È Stato Calcolato")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="path_to_target", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="current_target", access=py_trees.common.Access.READ)
        
    def setup(self):
        print("Setup IlPercorsoEStatoCalcolato")
        return True

    def initialise(self):
        pass

    def update(self):
        try:
            percorso = self.blackboard.path_to_target
            target_attuale = self.blackboard.current_target
        except KeyError:
            return py_trees.common.Status.FAILURE
        
        # Controlliamo che esista un percorso valido verso il target attuale
        if target_attuale is not None and isinstance(percorso, list) and len(percorso) > 0:
            print(f"[{self.name}] Il percorso verso il target {target_attuale} è stato calcolato.")
            return py_trees.common.Status.SUCCESS
        
        #Se non c'è un percorso significa che o c'è stato un errore
        #oppure sono arrivato al targhet ho effettuato un pickup/dropoff 
        #e ora devo decidere il prossimo target da raggiungere
        return py_trees.common.Status.FAILURE
    

class CalcolaPercorso(py_trees.behaviour.Behaviour):
    def __init__(self):
        print("Inizializzo nodo CalcolaPercorso")
        super(CalcolaPercorso, self).__init__(name="Calcola Percorso")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)

    def setup(self):
        print("Setup CalcolaPercorso")
        return True

    def initialise(self):
        pass

    def update(self):
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