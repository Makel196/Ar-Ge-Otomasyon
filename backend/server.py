from flask import Flask, request, jsonify
from flask_cors import CORS
import threading
import queue
import time
from pdm_logic import LogicHandler, read_vault_path_registry

app = Flask(__name__)
CORS(app)

# Global State
state = {
    "status": "Hazır",
    "progress": 0.0,
    "logs": [],
    "is_running": False,
    "vault_path": read_vault_path_registry()
}

# Queues
log_queue = queue.Queue()
status_queue = queue.Queue()
progress_queue = queue.Queue()

# Logic Handler Instance (will be recreated on start to ensure fresh state if needed, or reused)
# Actually, LogicHandler is designed to be instantiated once or per run. 
# Let's keep a reference.
logic_handler = None

# Settings
current_settings = {
    "add_to_existing": False,
    "stop_on_not_found": True
}

def get_add_to_existing():
    return current_settings["add_to_existing"]

def get_stop_on_not_found():
    return current_settings["stop_on_not_found"]

def background_worker():
    """Consumes queues and updates global state."""
    while True:
        try:
            # Logs
            while not log_queue.empty():
                log_entry = log_queue.get_nowait()
                state["logs"].append(log_entry)
                # Keep only last 1000 logs to avoid memory issues
                if len(state["logs"]) > 1000:
                    state["logs"].pop(0)
            
            # Status
            while not status_queue.empty():
                state["status"] = status_queue.get_nowait()
            
            # Progress
            while not progress_queue.empty():
                state["progress"] = progress_queue.get_nowait()
                
            time.sleep(0.1)
        except Exception:
            pass

# Start background worker
worker_thread = threading.Thread(target=background_worker, daemon=True)
worker_thread.start()

@app.route('/api/status', methods=['GET'])
def get_status():
    # Return logs since a given index if provided
    since_index = request.args.get('since', type=int)
    
    response = {
        "status": state["status"],
        "progress": state["progress"],
        "is_running": logic_handler.is_running if logic_handler else False,
        "vault_path": state["vault_path"]
    }
    
    if since_index is not None:
        if since_index < len(state["logs"]):
            response["logs"] = state["logs"][since_index:]
        else:
            response["logs"] = []
    else:
        response["logs"] = state["logs"]
        
    response["last_log_index"] = len(state["logs"])
    return jsonify(response)

@app.route('/api/start', methods=['POST'])
def start_process():
    global logic_handler
    data = request.json
    codes = data.get('codes', [])
    
    current_settings["add_to_existing"] = data.get('addToExisting', False)
    current_settings["stop_on_not_found"] = data.get('stopOnNotFound', True)
    
    if not codes:
        return jsonify({"error": "No codes provided"}), 400
        
    if logic_handler and logic_handler.is_running:
        return jsonify({"error": "Process already running"}), 400
        
    # Reset state
    state["logs"] = []
    state["progress"] = 0.0
    state["status"] = "Başlatılıyor..."
    
    logic_handler = LogicHandler(
        log_queue, 
        status_queue, 
        progress_queue, 
        get_add_to_existing, 
        get_stop_on_not_found
    )
    
    # Update vault path if needed
    if state["vault_path"]:
        logic_handler.vault_path = state["vault_path"]
        
    # Run in thread
    thread = threading.Thread(target=logic_handler.run_process, args=(codes,), daemon=True)
    thread.start()
    
    return jsonify({"message": "Started"})

@app.route('/api/stop', methods=['POST'])
def stop_process():
    if logic_handler:
        logic_handler.stop_process()
        return jsonify({"message": "Stopping..."})
    return jsonify({"message": "Not running"})

@app.route('/api/vault-path', methods=['GET', 'POST'])
def handle_vault_path():
    if request.method == 'POST':
        path = request.json.get('path', '')
        state["vault_path"] = path
        if logic_handler:
            logic_handler.set_vault_path(path)
        else:
            # If no handler yet, just update registry manually or wait for next start
            # But LogicHandler has the registry logic.
            # Let's instantiate a temp one or just use the function directly if imported
            # We imported read_vault_path_registry but not write.
            # Let's just update the state and let the next LogicHandler pick it up, 
            # or better, import write_vault_path_registry.
            from pdm_logic import write_vault_path_registry
            write_vault_path_registry(path)
            
        return jsonify({"path": path})
    else:
        return jsonify({"path": state["vault_path"]})

@app.route('/api/clear', methods=['POST'])
def clear_logs():
    state["logs"] = []
    state["progress"] = 0.0
    state["status"] = "Hazır"
    return jsonify({"message": "Cleared"})

if __name__ == '__main__':
    app.run(port=5000)
