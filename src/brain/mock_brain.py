# FILE: src/brain/mock_brain.py
import time
import sys
import os
import signal

sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

from modules.redis_interface import RedisInterface 

def main():
    """Mock brain entry point: publishes a scripted sequence of commands to Redis for manual testing."""
    print("🧠 Avvio MOCK BRAIN. Pubblicazione comandi su Redis...")

    BRAIN_KEY = "brain_memory"
    NODE_KEY = "am_i_in_a_node"
    
    redis_manager = RedisInterface() 
    if not redis_manager.db:
        print("[BRAIN] Errore critico: Uscita per mancata connessione a Redis.")
        return 
    
    redis_manager.update_sensor_data(BRAIN_KEY, {NODE_KEY: False})
    redis_manager.update_sensor_data(BRAIN_KEY, {"target_node": "EC"})
    redis_manager.update_sensor_data(BRAIN_KEY, {"previous_node": "E1"})

    def spegnimento_sicuro(signum, frame):
        """SIGTERM handler: converts Docker's stop signal into a KeyboardInterrupt."""
        print("\n[BRAIN] Ricevuto segnale di spegnimento da Docker (SIGTERM)!")
        raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, spegnimento_sicuro)

    print("[BRAIN] Inizio pubblicazione comandi...")
    
    try:
        '''
        # Comando 1: STOP
        print("\n1️⃣ Pubblicando STOP...")
        command = {"type": "STOP"}
        redis_manager.set_command(redis_manager.COMMAND_CHANNEL, command)
        time.sleep(3)
        '''
        pos = redis_manager.get_sensor_data(BRAIN_KEY).get("current_position")

        # Comando 2: MOVE_TO
        print("\n2️⃣ Pubblicando MOVE_TO I2...")
        command = {
            "type": "MOVE_TO",
            "next_node": "I2",
            "current_position": "I1",
            "am_i_in_a_node": True,
            "previous_node": "E1"
        }
        redis_manager.set_command(redis_manager.COMMAND_CHANNEL, command)
        time.sleep(10)

        '''
        # Comando 2: MOVE_TO
        print("\n2️⃣ Pubblicando MOVE_TO I2...")
        command = {
            "type": "MOVE_TO",
            "next_node": "I2",
            #"current_position": "I3",
            "am_i_in_a_node": True
        }
        redis_manager.set_command(redis_manager.COMMAND_CHANNEL, command)
        time.sleep(3)
        
        redis_manager.update_sensor_data(BRAIN_KEY, {NODE_KEY: True})
        print("\n3️⃣ Il sensore ha aggiornato che siamo in un nodo. ")
        time.sleep(3)

        print("\n2️⃣ Pubblicando MOVE_TO I6...")
        command = {
            "type": "MOVE_TO",
            "next_node": "I6",
            #"current_position": "I4",
            "am_i_in_a_node": True
        }
        redis_manager.set_command(redis_manager.COMMAND_CHANNEL, command)
        time.sleep(3)
        
        # Comando 3: STOP
        print("\n3️⃣ Pubblicando STOP...")
        command = {"type": "STOP"}
        redis_manager.set_command(redis_manager.COMMAND_CHANNEL, command)
        '''
        print("\n✅ Tutti i comandi pubblicati!")
        time.sleep(3)

    except KeyboardInterrupt:
        print("Spegnimento Brain...")

    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()