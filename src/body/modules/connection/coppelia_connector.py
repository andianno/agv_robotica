import os
import threading
from coppeliasim_zmqremoteapi_client import RemoteAPIClient

class CoppeliaConnector:
    """
    Manage multiple named connections to CoppeliaSim.

    The class implements a multiton pattern: the default ``main`` connection
    is shared, while additional names provide isolated connections for worker
    threads and actuators.
    """
    _instances = {}
    _lock = threading.Lock()

    def __new__(cls, name="main"):
        """Return the shared connector associated with ``name``.

        Args:
            name: Connection identifier. The default ``main`` name preserves
                compatibility with callers that use the primary connection.

        Returns:
            CoppeliaConnector: The existing named instance or a newly created
            instance when the name has not been registered yet.
        """
        with cls._lock:
            if name not in cls._instances:
                instance = super(CoppeliaConnector, cls).__new__(cls)
                instance._initialized = False
                cls._instances[name] = instance
        return cls._instances[name]

    def __init__(self, name="main"):
        """Configure and connect a named CoppeliaSim connector.

        The host and port are read from ``COPPELIA_HOST`` and
        ``COPPELIA_PORT``. Defaults are ``host.docker.internal`` and
        ``23000`` respectively.

        Args:
            name: Identifier of the connection instance.

        Returns:
            None.
        """
        # Se l'istanza con questo nome è già stata configurata, non fare nulla
        if self._initialized:
            return
            
        self.name = name
        self._client = None
        self._sim = None
        
        # Parametri di rete
        self.host = os.getenv('COPPELIA_HOST', 'host.docker.internal')
        self.port = int(os.getenv('COPPELIA_PORT', 23000))
        
        # Esegue la connessione immediata
        self.connect()
        self._initialized = True

    def connect(self):
        """Establish the CoppeliaSim connection for this instance.

        The connection is created only when no simulation object is already
        available. Connection failures are logged and represented by ``None``
        in ``self._sim``.

        Returns:
            object | None: The CoppeliaSim ``sim`` API object, or ``None`` when
            the connection cannot be established.
        """
        if self._sim is None:
            try:
                print(f"[CoppeliaConnector:{self.name}] Connessione a {self.host}:{self.port}...")
                self._client = RemoteAPIClient(host=self.host, port=self.port)
                self._sim = self._client.getObject('sim')
                print(f"[CoppeliaConnector:{self.name}] Connessione stabilita.")
            except Exception as e:
                print(f"[CoppeliaConnector:{self.name}] ERRORE: {e}")
                self._sim = None
        return self._sim

    def get_sim(self):
        """Return the CoppeliaSim API object for this connection.

        If the connection is not currently available, this method attempts to
        establish it before returning.

        Returns:
            object | None: The connected CoppeliaSim ``sim`` API object, or
            ``None`` when connection establishment fails.
        """
        if not self._sim:
            return self.connect()
        return self._sim