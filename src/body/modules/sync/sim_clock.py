import threading

class SimClock:
    """
    Coordinate simulation ticks and synchronization between Body threads.

    One tick corresponds to one completed ``sim.step()`` call. The clock
    replaces time-based sleeps as the synchronization primitive for threads
    that read sensors or send actuator commands.
    """

    def __init__(self):
        """Initialize an empty simulation clock.

        Returns:
            None.
        """
        self._step = 0
        self._cond = threading.Condition()
        self._participants = {}   # nome -> (periodo, primo_step_dovuto)
        self._acked = set()

    def register(self, name, period_steps):
        """Register a participant in the simulation barrier.

        The first due step is calculated and returned atomically as the
        current step plus the participant period. Callers must use this value
        as the first target for :meth:`wait_until` instead of reading
        ``current_step`` separately, which would reintroduce a race condition
        between the main loop and the participant thread.

        Args:
            name: Unique participant identifier used for acknowledgments.
            period_steps: Number of simulation steps between acknowledgments.

        Returns:
            int: First simulation step at which the participant must provide
            an acknowledgment.
        """
        with self._cond:
            first_due_step = self._step + period_steps
            self._participants[name] = (period_steps, first_due_step)
            self._cond.notify_all()
            return first_due_step

    def unregister(self, name):
        """Remove a participant from the simulation barrier.

        Args:
            name: Identifier of the participant to remove.

        Returns:
            None. Missing participant names are ignored.
        """
        with self._cond:
            self._participants.pop(name, None)
            self._cond.notify_all()

    def _due_now(self):
        """Return the participants due to acknowledge the current step.

        Returns:
            set[str]: Identifiers of participants whose configured period
            requires an acknowledgment at the current step.
        """
        due = set()
        for n, (period, first_due) in self._participants.items():
            if self._step >= first_due and (self._step - first_due) % period == 0:
                due.add(n)
        return due

    def advance(self):
        """Advance the clock by one simulation step.

        This method must only be called after ``sim.step()`` has completed,
        typically by the main loop or the cleanup stepper. Advancing resets
        the acknowledgment set for the new step and wakes waiting threads.

        Returns:
            None.
        """
        with self._cond:
            self._step += 1
            self._acked = set()
            self._cond.notify_all()

    def wait_until(self, target_step):
        """Block until the clock reaches a target simulation step.

        Args:
            target_step: Step number at which the caller may resume.

        Returns:
            int: The current step when the wait completes.
        """
        with self._cond:
            while self._step < target_step:
                self._cond.wait()
            return self._step

    def wait_for(self, names, step):
        """Wait for named participants to acknowledge a specific step.

        This provides an explicit read-after-write dependency within one
        simulation tick. The wait ends when all requested participants have
        acknowledged the step or when the clock advances beyond it.

        Args:
            names: Iterable of participant identifiers whose acknowledgments
                are required.
            step: Simulation step in which the acknowledgments are expected.

        Returns:
            None.
        """
        with self._cond:
            while self._step == step and not set(names).issubset(self._acked):
                self._cond.wait()

    def ack(self, name):
        """Acknowledge completion of the current simulation step.

        Args:
            name: Identifier of the participant sending the acknowledgment.

        Returns:
            None.
        """
        with self._cond:
            self._acked.add(name)
            self._cond.notify_all()

    def wait_barrier(self, timeout=None):
        """Wait until all due participants acknowledge the current step.

        This method is intended for the main simulation loop. If the barrier
        is not completed before the optional timeout, a ``RuntimeError`` is
        raised with the participants that have not acknowledged the step.

        Args:
            timeout: Maximum number of seconds to wait, or ``None`` to wait
                indefinitely.

        Returns:
            None.

        Raises:
            RuntimeError: If the barrier timeout expires before all due
                participants acknowledge the current step.
        """
        with self._cond:
            ok = self._cond.wait_for(
                lambda: self._due_now().issubset(self._acked), timeout=timeout
            )
            if not ok:
                missing = self._due_now() - self._acked
                raise RuntimeError(f"Barrier timeout: mancano ack da {missing} allo step {self._step}")

    @property
    def current_step(self):
        """Return the current simulation step.

        Returns:
            int: Current step counter, protected by the clock condition.
        """
        with self._cond:
            return self._step