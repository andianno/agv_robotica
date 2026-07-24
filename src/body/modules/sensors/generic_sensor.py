class GenericSensor:
    """Base interface for sensors used by the Body service."""

    def __init__(self, name):
        """Initialize a sensor with its simulator object name.

        Args:
            name: Name or path used to identify the sensor in the simulator.

        Returns:
            None.
        """
        self.name = name

    def read(self):
        """Read and return the sensor's current measurement.

        Returns:
            object: Sensor-specific measurement data.

        Raises:
            NotImplementedError: Always raised by the base class. Concrete
                sensors must implement this method.
        """
        raise NotImplementedError("Subclasses must implement read()")
