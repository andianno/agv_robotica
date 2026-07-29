import time
import py_trees
from py_trees.common import Status

# =============================================================================
# 4. OPERATIVE NODES FOR PICKUP AND DELIVERY
# =============================================================================


class ENodoDiPrelievo(py_trees.behaviour.Behaviour):
    """
    Condition: checks whether the AGV has physically arrived at a pickup node.
    """
    def __init__(self):
        """Registers read access to the mission queue, current position and load state on the blackboard."""
        super(ENodoDiPrelievo, self).__init__(name="E' Nodo di Prelievo?")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="mission_queue", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="current_position", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="am_i_in_a_node", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="is_load", access=py_trees.common.Access.READ)

    def setup(self):
        """py_trees lifecycle hook, called once when the tree is set up."""
        print("Setup ENodoDiPrelievo")
        return True

    def initialise(self):
        """py_trees lifecycle hook, called once each time this node starts running. Nothing to do here."""
        pass

    def update(self):
        """Returns SUCCESS if the AGV is on the pickup node and not already loaded, FAILURE otherwise."""
        try:
            target = self.blackboard.mission_queue[0].get('pick_up_position') if self.blackboard.mission_queue else None
            pos_attuale = self.blackboard.current_position
            am_i_in_a_node = self.blackboard.am_i_in_a_node
            is_load = self.blackboard.is_load
        except KeyError:
            return py_trees.common.Status.FAILURE

        if target is None:
            return py_trees.common.Status.FAILURE
        
        if is_load:
            return py_trees.common.Status.FAILURE
        
        # NOTE : if we work here with current_target instead of mission_queue[pick_up_position],
        # we will have to update current_target after the pickup is completed
        if pos_attuale == target and am_i_in_a_node:
            return py_trees.common.Status.SUCCESS
        
        return py_trees.common.Status.FAILURE


class EseguiPrelievo(py_trees.behaviour.Behaviour):
    """
    Action: sends the PICKUP command to the Body and waits for sensor feedback.
    """
    def __init__(self):
        """Registers read access to the current target, load state and the shared logic_controller on the blackboard."""
        super(EseguiPrelievo, self).__init__(name="Esegui Prelievo")
        self.blackboard = py_trees.blackboard.Client(name=self.name)

        # Registriamo le chiavi in lettura
        self.blackboard.register_key(key="current_target", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="is_load", access=py_trees.common.Access.READ)

    def setup(self):
        """py_trees lifecycle hook, called once when the tree is set up."""
        print(f"Setup {self.name}")
        return True

    def initialise(self):
        """ Run ONCE when this node starts. Sends the pickup command. """
        try:
            lc = self.blackboard.logic_controller
            print(f"[{self.name}] 📦 Invio comando di PICKUP ai motori...")
            
            lc.esegui_prelievo()  # Metodo che imposta il comando di PICKUP sul DB, da cui il Mock Body leggerà
            
        except KeyError:
            print(f"[{self.name}] ERRORE: Logic Controller non trovato sulla Blackboard!")
            pass # Non possiamo restituire FAILURE qui, lo farà l'update al prossimo tick

    def update(self):
        """ Run CONTINUOUSLY while it returns RUNNING. Reads sensor feedback. """
        try:
            is_load = self.blackboard.is_load # In questo caso, il feedback che ci interessa è se il carico è stato sollevato, non tanto lo stato delle forche
        except KeyError:
            return py_trees.common.Status.FAILURE

        # 1. Se le forche non sono ancora alzate, stiamo in silenzio e aspettiamo
        if not is_load:
            return py_trees.common.Status.RUNNING
        print(f"[{self.name}] ✅ Feedback ricevuto: Forche alzate con successo, carico a bordo!")
        return py_trees.common.Status.SUCCESS

class ENodoDiConsegna(py_trees.behaviour.Behaviour):
    """
    Condition: checks whether the current node is a delivery point.
    """
    def __init__(self):
        """Registers read access to the mission queue, current position and load state on the blackboard."""
        super(ENodoDiConsegna, self).__init__(name="È Nodo di Consegna")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="mission_queue", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="current_position", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="am_i_in_a_node", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="is_load", access=py_trees.common.Access.READ)

    def setup(self):
        """py_trees lifecycle hook, called once when the tree is set up."""
        print("Setup ENodoDiConsegna")
        return True

    def initialise(self):
        """py_trees lifecycle hook, called once each time this node starts running. Nothing to do here."""
        pass

    def update(self):
        """Returns SUCCESS if the AGV is loaded and on the delivery node, FAILURE otherwise."""
        try:
            target = self.blackboard.mission_queue[0].get('destination') if self.blackboard.mission_queue else None
            pos_attuale = self.blackboard.current_position
            am_i_in_a_node = self.blackboard.am_i_in_a_node
            is_load = self.blackboard.is_load
        except KeyError:
            return py_trees.common.Status.FAILURE

        if target is None:
            return py_trees.common.Status.FAILURE
        
        if not is_load:
            return py_trees.common.Status.FAILURE
        
        if pos_attuale == target and am_i_in_a_node:
            return py_trees.common.Status.SUCCESS
        
        return py_trees.common.Status.FAILURE

class EseguiConsegna(py_trees.behaviour.Behaviour):
    """
    Action: sends the DROP command to the Body and waits for sensor feedback.
    """
    def __init__(self):
        """Registers read access to the load state and the shared logic_controller on the blackboard."""
        super(EseguiConsegna, self).__init__(name="Esegui Consegna")
        self.blackboard = py_trees.blackboard.Client(name=self.name)

        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="is_load", access=py_trees.common.Access.READ)

    def setup(self):
        """py_trees lifecycle hook, called once when the tree is set up."""
        print(f"Setup {self.name}")
        return True

    def initialise(self):
        """ Run ONCE when this node starts. Sends the drop command. """
        try:
            lc = self.blackboard.logic_controller
            print(f"[{self.name}] 📦 Invio comando di DROP ai motori...")
            
            lc.esegui_consegna()
            
        except KeyError:
            print(f"[{self.name}] ERRORE: Logic Controller non trovato sulla Blackboard!")

    def update(self):
        """ Run CONTINUOUSLY while it returns RUNNING. Reads sensor feedback. """
        try:
            is_load = self.blackboard.is_load
            lc = self.blackboard.logic_controller
        except KeyError:
            return py_trees.common.Status.FAILURE
         
        # While we still have the load on board, the DROP action is still in progress, we wait for it to be released
        if is_load:
            return py_trees.common.Status.RUNNING
        print(f"[{self.name}] ✅ Feedback ricevuto: Forche abbassate con successo, carico rilasciato!")
        return py_trees.common.Status.SUCCESS        
            