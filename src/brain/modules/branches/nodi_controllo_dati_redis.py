import time
import py_trees
from py_trees.common import Status

# =============================================================================
# 0. REDIS NODES MANAGEMENT
# =============================================================================

class RedisDataNotReady(py_trees.behaviour.Behaviour):
    """
    Checks whether the required data is ready on Redis.
    Returns SUCCESS if the data is NOT ready yet (triggering the wait sequence).
    """
    def __init__(self):
        """Registers read access to the shared logic_controller on the blackboard."""
        super(RedisDataNotReady, self).__init__(name="Controllo Dati Redis")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)

    def setup(self):
        """py_trees lifecycle hook, called once when the tree is set up."""
        print("Setup Controllo Dati Redis")
        return True

    def initialise(self):
        """py_trees lifecycle hook, called once each time this node starts running. Nothing to do here."""
        pass

    def update(self):
        """Returns SUCCESS if Redis data is not ready yet, FAILURE if it is."""
        esito = self.blackboard.logic_controller.check_redis_data()
        if not esito:
            print("[ControlloDatiRedis] Dati non pronti su Redis. Attivo sequenza di attesa.")
            return Status.SUCCESS
        else:
            return Status.FAILURE

class WaitRedis(py_trees.behaviour.Behaviour):
    """
    Wait node that stays RUNNING until the Redis data becomes ready.
    """
    def __init__(self):
        """Sets up the fixed wait duration (in seconds) before this node reports SUCCESS."""
        super(WaitRedis, self).__init__(name="Wait Redis")
        self.duration = 1.0 # Durata dell'attesa in secondi
        self.start_time = None

    def setup(self):
        """py_trees lifecycle hook, called once when the tree is set up."""
        print("Setup Wait Redis")
        return True

    def initialise(self):
        """Starts the wait timer each time this node begins running."""
        self.start_time = time.time()
        print("[WaitRedis] Attendo che i dati siano pronti su Redis...")

    def update(self):
        """Returns SUCCESS once the wait duration has elapsed, RUNNING otherwise."""
        elapsed_time = time.time() - self.start_time
        if elapsed_time >= self.duration:
            print("[WaitRedis] Dati ora pronti su Redis. Passo alla fase successiva.")
            return Status.SUCCESS
        else:
            return Status.RUNNING
