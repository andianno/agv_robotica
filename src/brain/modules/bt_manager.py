import py_trees
import time
from py_trees.common import Status
from .branches.nodi_controllo_dati_redis import *
from .branches.nodi_energia import *
from .branches.nodi_missione import *
from .branches.nodi_operativi import *
from .branches.nodi_sicurezza import *

# =============================================================================
# BEHAVIOR TREE CREATION
# =============================================================================

def crea_albero_agv():
    """
    Builds and returns the complete Behavior Tree structure.
    """
    # Elemento Root: Selettore Principale (Priorità: Sicurezza -> Energia -> Missione)
    root = py_trees.composites.Selector("Selettore Principale", memory=False)

    # --- BRANCH 0: CONTROLLO DATI PRONTI DA REDIS ---
    sequenza_controllo_dati_redis = py_trees.composites.Sequence("Controllo Dati Redis", memory=True)
    controllo_dati_redis = RedisDataNotReady()
    wait_redis = WaitRedis()
    sequenza_controllo_dati_redis.add_children([controllo_dati_redis, wait_redis])

    # --- BRANCH 1: PERSON SAFETY ---
    # Sequence: If a person is detected -> Stop -> Wait
    sequenza_sicurezza = py_trees.composites.Sequence("Sicurezza Persona" , memory=False)
    controllo_persona = ControllaOstacolo()
    stop_motori = StopMotori()
    aspetta = Aspetta()
    sequenza_sicurezza.add_children([controllo_persona, stop_motori, aspetta])

    # --- BRANCH 2: ENERGY MANAGEMENT ---
    # Sequence: If battery is low -> Calculate Charging Path -> Go -> Charge
    sequenza_energia = py_trees.composites.Sequence("Gestione Energia", memory=True)
    controllo_batteria = ControlloBatteria()
    calcola_percorso_ricarica = CalcolaPercorsoRicarica()
    vai_a_ricarica = VaiAStazioneRicarica()
    ricarica_batteria = RicaricaBatteria()
    sequenza_energia.add_children([controllo_batteria, calcola_percorso_ricarica, vai_a_ricarica, ricarica_batteria])

# --- BRANCH 3: ENERGY MANAGEMENT  ---
    # Choses between Planning (if the queue is empty) or Execution (if we already have a target)
    selettore_missione = py_trees.composites.Selector("Gestione Missione", memory=True)

    # 3.1: Pianification Step (Generate Plan)
    sequenza_pianificazione = py_trees.composites.Sequence("Generazione Piano", memory=False)
    piano_non_generato = PianoNonGenerato()
    ricevi_lista = RiceviListaPallet() # Questo nodo ora fa da Guardiano (IDLE se lista vuota)
    genera_piano = GeneraPianoOttimale()
    sequenza_pianificazione.add_children([piano_non_generato, ricevi_lista, genera_piano])

    # 3.2: Execution Step (Navigate to Target and Perform Pickup/Delivery)
    sequenza_esecuzione = py_trees.composites.Sequence("Esecuzione Step", memory=True)
    vai_a_target = NavigaVersoTarget()
    # 3.2.1: Generate Path to Target (if not already calculated)
    selettore_percorso = py_trees.composites.Selector("Generazione Percorso", memory=False)
    condizione_percorso = IlPercorsoEStatoCalcolato()
    calcola_percorso = CalcolaPercorso()
    selettore_percorso.add_children([condizione_percorso, calcola_percorso])

    # 3.2.2: In node operation, choose between Pickup or Delivery based on the current target's action type
    selettore_operazione = py_trees.composites.Selector("Operazione Nodo", memory=True)

    # Branch for Pickup Operation
    sequenza_ritiro = py_trees.composites.Sequence("Ritiro", memory=True)  
    e_prelievo = ENodoDiPrelievo()
    esegui_prelievo = EseguiPrelievo()
    sequenza_ritiro.add_children([e_prelievo, esegui_prelievo])

    # Branch for Delivery Operation
    sequenza_consegna = py_trees.composites.Sequence("Consegna", memory=True)
    e_consegna = ENodoDiConsegna()
    esegui_consegna = EseguiConsegna()  
    sequenza_consegna.add_children([e_consegna, esegui_consegna])

    # Sub-tree assemblation for the operation selector: choose between Pickup and Delivery
    selettore_operazione.add_children([sequenza_ritiro, sequenza_consegna])
    sequenza_esecuzione.add_children([selettore_percorso, vai_a_target,selettore_operazione])

    # Sub-tree assemblation for the mission selector: choose between Planning and Execution
    selettore_missione.add_children([sequenza_pianificazione, sequenza_esecuzione])

    # Root tree assemblation: add all main branches to the root selector
    root.add_children([sequenza_controllo_dati_redis, sequenza_sicurezza, sequenza_energia, selettore_missione])

    return root