class GenericActuator:
    """Base interface for actuators used by the Body service.

    Concrete actuators, such as wheel, arm, or lift actuators, should inherit
    from this class and implement the movement and stop operations defined
    below.
    """

    def __init__(self, name):
        """Create an actuator with a human-readable identifier.

        Args:
            name: Identifier used to distinguish this actuator in logs and
                controller configuration.

        Returns:
            None.
        """
        self.name = name

    def move(self, *args, **kwargs):
        """Command the actuator to move.

        This method defines the interface expected by actuator subclasses.
        The accepted positional and keyword arguments depend on the concrete
        actuator implementation, for example a target position or velocity.

        Args:
            *args: Positional arguments required by the concrete actuator.
            **kwargs: Keyword arguments required by the concrete actuator.

        Returns:
            None. Concrete implementations may define a more specific return
            value if the calling controller requires one.

        Raises:
            NotImplementedError: Always raised by the base class. Subclasses
                must override this method.
        """
        raise NotImplementedError("Subclasses must implement the move() method")

    def stop(self):
        """Stop the actuator and bring it to a safe idle state.

        This method defines the interface expected by actuator subclasses.
        Concrete implementations are responsible for sending the appropriate
        stop command to the underlying hardware or simulator.

        Args:
            None.

        Returns:
            None.

        Raises:
            NotImplementedError: Always raised by the base class. Subclasses
                must override this method.
        """
        raise NotImplementedError("Subclasses must implement the stop() method")