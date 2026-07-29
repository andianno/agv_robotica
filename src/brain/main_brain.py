# FILE: src/brain/main_brain.py 
import time
import sys
import os
import shutil
import py_trees
import signal # To handle process interruption with Ctrl+C

sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

from modules.bt_manager import crea_albero_agv
from modules.redis_interface import RedisInterface 
from modules.logic_controller import LogicController 

def main():
    """Initializes Redis, the Logic Controller, the blackboard and the Behavior Tree, then runs the main tick loop until shutdown."""
    print("🧠 Avvio BRAIN. Implementazione Logic Controller su Redis Pub/Sub...")
    
    # REMOVE the ready file at startup, if it exists (from a previous run)
    ready_file = "/tmp/brain_ready"
    if os.path.exists(ready_file):
        os.remove(ready_file)
        print(f"⚠️  File di ready precedente rimosso: {ready_file}")
    
    # --- RESTORE INFO_PACK FROM BACKUP ---
    info_pack_path = os.path.join(os.path.dirname(__file__), 'docs', 'plan.json')
    backup_path = os.path.join(os.path.dirname(__file__), 'docs', 'plan-backup.json')
    try:
        if os.path.exists(backup_path):
            shutil.copy2(backup_path, info_pack_path)
            print(f"✓ info_pack.json ripristinato dal backup")
    except Exception as e:
        print(f"⚠ Avviso: Impossibile ripristinare info_pack.json dal backup: {e}")
    
    redis_manager = RedisInterface() 
    if not redis_manager.db:
        print("[BRAIN] Errore critico: Uscita per mancata connessione a Redis.")
        return 
    
    # --- INIZIALIZATION LOGIC CONTROLLER ---
    logic_controller = LogicController(redis_manager) 
       
    # --- INIZIALIZATION BLACKBOARD ---
    # Create a  client to write/read data in the BT Blackboard
    blackboard_client = py_trees.blackboard.Client(name="ClientBrain")
    # Register the key for the Logic Controller, which will be a shared object
    blackboard_client.register_key(key="logic_controller", access=py_trees.common.Access.WRITE)
    blackboard_client.logic_controller = logic_controller

    # Creation and setup of the Behavior Tree  
    behavior_tree = crea_albero_agv() 
    tree_executor = py_trees.trees.BehaviourTree(behavior_tree)
    tree_executor.setup(timeout=15) 

    # BRAIN COMPLETELY INITIALIZED - Create file for health check
    ready_file = "/tmp/brain_ready"
    open(ready_file, 'a').close()
    print(f"✅ Brain completamente avviato. File di ready creato: {ready_file}")

    def spegnimento_sicuro(signum, frame):
        """SIGTERM handler: converts Docker's stop signal into a KeyboardInterrupt to exit the main loop cleanly."""
        print("\n[BRAIN] Ricevuto segnale di spegnimento da Docker (SIGTERM)!")
        raise KeyboardInterrupt() # Scatena l'eccezione che ti fa uscire dal while!

    # When a SIGTERM is received or Docker compose down is called it will call spegnimento_sicuro, which raises a KeyboardInterrupt to exit the main loop cleanly.
    signal.signal(signal.SIGTERM, spegnimento_sicuro)

    print("[BRAIN] Ingresso nel ciclo principale...")
    try:
        while True:
            
            #update of the blackboard with the processed sensor data coming from Redis
            logic_controller.update_blackboard_reading_from_redis()
            
            #tick of the BT
            tree_executor.tick()
            
            #The brain make a tick every 100ms (10Hz)
            time.sleep(0.1) 

    except KeyboardInterrupt:
        print("Spegnimento Brain...")
        if os.path.exists(ready_file):
            os.remove(ready_file)

if __name__ == "__main__":
    main()