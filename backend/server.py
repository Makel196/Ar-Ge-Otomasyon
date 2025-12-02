import sys
import os
import signal
import threading
import queue
import time
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from pdm_logic import LogicHandler, read_vault_path_registry, write_vault_path_registry

# Disable Flask default logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

class AutomationServer:
    def __init__(self):
        self.app = Flask(__name__)
        CORS(self.app)
        self.state_lock = threading.Lock()
        
        # State Management
        self.state = {
            "status": "Sistem Hazır",
            "progress": 0.0,
            "logs": [],
            "is_running": False,
            "is_paused": False,
            "vault_path": read_vault_path_registry(),
            "stats": {"total": 0, "success": 0, "error": 0}
        }
        
        # Queues
        self.log_queue = queue.Queue()
        self.status_queue = queue.Queue()
        self.progress_queue = queue.Queue()
        self.stats_queue = queue.Queue()
        
        # Logic Handler
        self.logic_handler = None
        
        # Settings
        self.current_settings = {
            "add_to_existing": False,
            "stop_on_not_found": True
        }
        
        # Setup
        self.setup_routes()
        self.setup_background_worker()
        self.setup_signal_handlers()

    def get_add_to_existing(self):
        return self.current_settings["add_to_existing"]

    def get_stop_on_not_found(self):
        return self.current_settings["stop_on_not_found"]

    def setup_signal_handlers(self):
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

    def shutdown(self, signum, frame):
        print(f"Received signal {signum}. Shutting down...", flush=True)
        if self.logic_handler:
            self.logic_handler.stop_process()
        sys.exit(0)

    def setup_background_worker(self):
        def worker():
            print("Background worker started", flush=True)
            while True:
                try:
                    # Logs
                    while not self.log_queue.empty():
                        log_entry = self.log_queue.get_nowait()
                        with self.state_lock:
                            self.state["logs"].append(log_entry)
                            if len(self.state["logs"]) > 1000:
                                self.state["logs"].pop(0)
                    
                    # Status
                    while not self.status_queue.empty():
                        status = self.status_queue.get_nowait()
                        with self.state_lock:
                            self.state["status"] = status
                    
                    # Progress
                    while not self.progress_queue.empty():
                        progress = self.progress_queue.get_nowait()
                        with self.state_lock:
                            self.state["progress"] = progress
                    
                    # Stats
                    while not self.stats_queue.empty():
                        new_stats = self.stats_queue.get_nowait()
                        with self.state_lock:
                            # Explicitly update fields to ensure no overwrite issues
                            current = self.state["stats"]
                            current["total"] = new_stats.get("total", current["total"])
                            current["success"] = new_stats.get("success", current["success"])
                            current["error"] = new_stats.get("error", current["error"])
                            print(f"Server stats updated: {self.state['stats']}", flush=True)
                        
                    time.sleep(0.1)
                except Exception as e:
                    print(f"Worker error: {e}", flush=True)
        
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def setup_routes(self):
        @self.app.route('/api/status', methods=['GET'])
        def get_status():
            since_index = request.args.get('since', 0, type=int)
            
            with self.state_lock:
                response = {
                    "status": self.state["status"],
                    "progress": self.state["progress"],
                    "is_running": self.state["is_running"],
                    "is_paused": self.state["is_paused"],
                    "vault_path": self.state["vault_path"],
                    "stats": self.state.get("stats", {"total": 0, "success": 0, "error": 0})
                }
                
                if since_index < len(self.state["logs"]):
                    response["logs"] = self.state["logs"][since_index:]
                else:
                    response["logs"] = []
                    
                response["last_log_index"] = len(self.state["logs"])
            
            # Update running state from logic handler if available
            if self.logic_handler:
                response["is_running"] = self.logic_handler.is_running
                response["is_paused"] = self.logic_handler.is_paused
                
            return jsonify(response)

        @self.app.route('/api/start', methods=['POST'])
        def start_process():
            data = request.json
            codes_text = data.get('codes', [])
            # Handle both string (newline separated) and list
            if isinstance(codes_text, str):
                codes = [c.strip() for c in codes_text.split('\n') if c.strip()]
            else:
                codes = codes_text
            
            self.current_settings["add_to_existing"] = data.get('addToExisting', False)
            self.current_settings["stop_on_not_found"] = data.get('stopOnNotFound', True)
            
            # If multiKitMode is active, force disable other settings
            if data.get('multiKitMode', False):
                self.current_settings["add_to_existing"] = False
                self.current_settings["stop_on_not_found"] = False
                # Dedupe logic is handled in frontend before sending codes, but we can also ensure it here if needed
                # For now, we trust the frontend sent the raw codes or deduped codes based on its logic

            
            if not codes:
                return jsonify({"error": "No codes provided"}), 400
                
            if self.logic_handler and self.logic_handler.is_running:
                return jsonify({"error": "Process already running"}), 400
            
            # Clear queues to prevent stale data
            with self.stats_queue.mutex:
                self.stats_queue.queue.clear()
            with self.log_queue.mutex:
                self.log_queue.queue.clear()
            with self.status_queue.mutex:
                self.status_queue.queue.clear()
            with self.progress_queue.mutex:
                self.progress_queue.queue.clear()
                
            with self.state_lock:
                # Reset state
                self.state["logs"] = []
                self.state["progress"] = 0.0
                self.state["status"] = "Başlatılıyor..."
                self.state["is_running"] = True
                self.state["is_paused"] = False
                self.state["stats"] = {"total": len(codes), "success": 0, "error": 0}
            
            self.logic_handler = LogicHandler(
                self.log_queue, 
                self.status_queue, 
                self.progress_queue, 
                self.get_add_to_existing, 
                self.get_stop_on_not_found,
                self.stats_queue
            )
            
            if self.state["vault_path"]:
                self.logic_handler.vault_path = self.state["vault_path"]
                
            thread = threading.Thread(target=self.logic_handler.run_process, args=(codes,), daemon=True)
            thread.start()
            
            return jsonify({"message": "Started"})

        @self.app.route('/api/stop', methods=['POST'])
        def stop_process():
            if self.logic_handler:
                self.logic_handler.stop_process()
                with self.state_lock:
                    self.state["is_running"] = False
                return jsonify({"message": "Stopping..."})
            return jsonify({"message": "Not running"})

        @self.app.route('/api/pause', methods=['POST'])
        def pause_process():
            if self.logic_handler:
                self.logic_handler.pause_process()
                with self.state_lock:
                    self.state["is_paused"] = True
                return jsonify({"message": "Pausing..."})
            return jsonify({"message": "Not running"})

        @self.app.route('/api/resume', methods=['POST'])
        def resume_process():
            if self.logic_handler:
                self.logic_handler.resume_process()
                with self.state_lock:
                    self.state["is_paused"] = False
                return jsonify({"message": "Resuming..."})
            return jsonify({"message": "Not running"})

        @self.app.route('/api/vault-path', methods=['GET', 'POST'])
        def handle_vault_path():
            if request.method == 'POST':
                path = request.json.get('path', '')
                with self.state_lock:
                    self.state["vault_path"] = path
                if self.logic_handler:
                    self.logic_handler.set_vault_path(path)
                else:
                    write_vault_path_registry(path)
                return jsonify({"path": path})
            else:
                with self.state_lock:
                    return jsonify({"path": self.state["vault_path"]})

        @self.app.route('/api/clear', methods=['POST'])
        def clear_logs():
            with self.state_lock:
                self.state["logs"] = []
                self.state["progress"] = 0.0
                self.state["status"] = "Hazır"
                self.state["stats"] = {"total": 0, "success": 0, "error": 0}
            return jsonify({"message": "Cleared"})

    def run(self):
        print("Starting Automation Server on port 5000...", flush=True)
        # use_reloader=False is important for signal handling and to avoid double execution
        self.app.run(port=5000, use_reloader=False)

if __name__ == '__main__':
    # Ensure stdout is unbuffered for Electron to capture logs immediately
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    
    server = AutomationServer()
    server.run()
