import threading
import time
from modules.connection.redis_interface import RedisInterface
from modules.actuators.wheel_actuator import WheelsActuator
from modules.controllers.path_controller import PathController
from modules.actuators.cart_actuator import CartActuator

class ManueverController:
    # Costanti dei sensori
    LEFT_SENSOR_NAME = "/Robot/leftColorSensor"
    CENTER_SENSOR_NAME = "/Robot/centralColorSensor"
    RIGHT_SENSOR_NAME = "/Robot/rightColorSensor"
    BLACK_TARGET = [22, 22, 22]

    def __init__(self, redis_client: RedisInterface, clock):
        self.redis_client = redis_client
        self.clock = clock
        self.wheels = WheelsActuator()
        self.path_controller = PathController()
        self.cart = CartActuator()

        # Lock per evitare race condition su wheel_actuator
        self._wheel_lock = threading.Lock()
        self._cart_lock = threading.Lock()  # Lock per evitare race condition

        # Passo fisico della simulazione: usato per convertire le durate in
        # secondi (API esistente, invariata) in un numero deterministico di
        # step del SimClock.
        self.physical_dt = self.wheels.sim.getSimulationTimeStep()

    def execute_maneuver(self, command_type, command_data=None, retro = False, pid = None):
        """
        Avvia un thread per eseguire la manovra.
        Il thread è daemon, quindi termina automaticamente quando finisce.
        """
        maneuver_thread = threading.Thread(
            target=self._execute_maneuver_thread,
            args=(command_type, command_data, retro, pid),
            daemon=True
        )
        maneuver_thread.start()

    def _execute_maneuver_thread(self, command_type, command_data, retro, pid = None):
        """
        Esecuzione effettiva della manovra all'interno del thread.
        Termina automaticamente quando finisce.
        """
        self.pid = pid  # Store pid as instance attribute
        self.redis_client.update_sensor_data("body_memory", {"maneuver_state": "IN_PROGRESS"})
        print(f"🚀 Esecuzione manovra: {command_type} con dati: {command_data}")
        if command_type == "MOVE_TO":

            # Chiedi al PathController quale manovra fare (LEFT, RIGHT, STRAIGHT)
            maneuver_direction = self.path_controller.get_next_step2(
                command_data.get("current_position"),
                command_data.get("next_node"),
                command_data.get("previous_node")
            )
            print(f"🚗 PathController ha deciso la manovra: {maneuver_direction}")


            if maneuver_direction == "STRAIGHT":
                self.set_velocity_for(0.05, 0, 2)
                print(f"✅ Manovra STRAIGHT completata.")

            elif (maneuver_direction == "LEFT" and not retro) or (maneuver_direction == "RIGHT" and retro):
                self._execute_left_turn(reversed=retro)
                print(f"✅ Manovra di svolta a sinistra completata.")

            elif (maneuver_direction == "RIGHT" and not retro) or (maneuver_direction == "LEFT" and retro):
                self._execute_right_turn(reversed=retro)
                print(f"✅ Manovra di svolta a destra completata.")

            self.stop()  # Ferma il robot dopo la manovra
            # Segnala il completamento della manovra
            self.redis_client.update_sensor_data("body_memory", {"maneuver_state": "COMPLETED"})
            print(f"🧠 [ManeuverController] Manovra completata")

        elif command_type == "DROP":

            self.set_cart_open()
            print(f"✅ Manovra DROP completata.")

            # Segnala il completamento della manovra
            self.redis_client.update_sensor_data("body_memory", {"maneuver_state": "COMPLETED"})
            self.redis_client.update_sensor_data("brain_memory", {"is_load": False})

            #self.stop()

        elif command_type == "PICKUP":
            self.set_cart_close()
            print(f"✅ Manovra PICKUP completata.")

            # Segnala il completamento della manovra
            self.redis_client.update_sensor_data("body_memory", {"maneuver_state": "COMPLETED"})
            self.redis_client.update_sensor_data("brain_memory", {"is_load": True})

            #self.stop()



    def _execute_left_turn(self, reversed = False, pid = None):
        """
        Esegue una svolta a sinistra finché il sensore sinistro vede nero
        e il sensore destro non vede nero.
        """
        print("🔄 Inizio svolta SINISTRA...")
        direction = 1 if not reversed else -1

        self.set_velocity_for(0.0, 0.2, 7.85)  # Ruota a sinistra (w positivo)

        self.set_velocity_for(0.0, 0.0, 0.5)  # Ferma il robot dopo la svolta

        self.set_velocity_for(0.03*direction, 0.0, 3)  # Avanza leggermente per riagganciare il pid

    def _execute_right_turn(self, reversed = False, pid = None):
        """
        Esegue una svolta a destra finché il sensore destro vede nero
        e il sensore sinistro non vede nero.
        """
        print("🔄 Inizio svolta DESTRA...")
        direction = 1 if not reversed else -1
        self.set_velocity_for(0.0, -0.2, 7.85)  # Ruota a destra (w negativo)

        self.set_velocity_for(0.0, 0.0, 0.5)  # Ferma il robot dopo la svolta

        self.set_velocity_for(0.03*direction, 0.0, 3)  # Avanza leggermente per riagganciare il pid


    def set_velocity(self, v, w):
        """
        Comanda i wheel in modo thread-safe.
        Scrittura 'nuda': va chiamata SOLO da dentro un loop già gated
        sul SimClock (es. il PID, che fa il proprio ack subito dopo).
        """
        with self._wheel_lock:
            self.wheels.move(v, w)

    def set_velocity_for(self, v, w, duration, participant_name="maneuver"):
        duration_steps = max(1, round(duration / self.physical_dt))
        next_step = self.clock.register(participant_name, 1)
        try:
            for _ in range(duration_steps):
                actual = self.clock.wait_until(next_step)
                with self._wheel_lock:
                    self.wheels.move(v, w)
                self.clock.ack(participant_name)
                next_step = actual + 1
        finally:
            self.clock.unregister(participant_name)

    def set_cart_open(self):
        """
        Comanda l'apertura del carrello in modo thread-safe.
        Usato sia da PID che da TaskController/Maneuver.
        """
        with self._cart_lock:
            self.cart.open()

    def set_cart_close(self):
        """
        Comanda la chiusura del carrello in modo thread-safe.
        Usato sia da PID che da TaskController/Maneuver.
        """
        with self._cart_lock:
            self.cart.close()


    def stop(self):
        """
        Ferma il robot immediatamente.
        Stessa garanzia di set_velocity_for: un solo tick gated, così anche
        l'arresto avviene in modo sincronizzato e non in una finestra
        temporale variabile.
        """
        self.set_velocity_for(0.0, 0.0, self.physical_dt, participant_name="maneuver_stop")