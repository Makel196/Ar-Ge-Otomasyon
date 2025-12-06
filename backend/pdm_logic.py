import json
import os
import sys
import time
import ctypes
import threading
import win32com.client
import win32gui
import win32con
import pythoncom
import winreg
from queue import Queue
from sap_logic import SapGui

# --- Konfigürasyon ve Sabitler ---
VAULT_NAME = "PGR2024"
CONFIG_PATH = "config.json"
REG_PATH = r"Software\PDM_Montaj_Sihirbazi"
REG_VALUE_NAME = "VaultPath"

# PDM GetFileCopy Flag - En son revizyonu çekmek için
EGCF_GET_LATEST_REVISION = 65536  # EdmGetCmdFlags.Egcf_GetLatestRevision

PDM_VAR_NAMES = [
    "SAP Numarası",
    "SAP Numarasi",
    "SAP No",
    "SAP NO",
]

PREFERRED_EXTS = {".sldprt", ".sldasm"}

# SolidWorks Sabitleri
SW_DEFAULT_TEMPLATE_KEYS = (8, 1)
SW_DOC_PART = 1
SW_DOC_ASSEMBLY = 2
SW_OPEN_SILENT = 64
SW_MATE_COINCIDENT = 0
TEMPLATE_OVERRIDE = ""

# --- PDM Dialog İzleyici (Checkout dialoglarını otomatik iptal eder) ---

class PDMDialogWatcher:
    """
    PDM "Kasadan Al" (Check Out) dialoglarını izler ve otomatik olarak İptal eder.
    Arka planda thread olarak çalışır.
    """
    def __init__(self):
        self._running = False
        self._thread = None
        # Dialog başlıkları (Türkçe ve İngilizce)
        self._dialog_titles = [
            "SOLIDWORKS PDM",  # Ana PDM dialog başlığı
            "Kasadan Al",  # Turkish
            "Check Out",   # English
            "Kullanıma Al",  # Alternative Turkish
            "Get Latest Version",  # English alternative
            "Son Sürümü Al",  # Turkish alternative
            "Sorun Ne", # SolidWorks Error Dialog
            "What's Wrong", # SolidWorks Error Dialog English
        ]
        # İptal/Hayır button metinleri (Hayır'ı tercih et)
        self._cancel_texts = ["Hayır", "İptal", "No", "Cancel", "Vazgeç", "Kapat", "Close"]
    
    def _find_button_by_text(self, parent_hwnd, texts):
        """Verilen metinlerden birine sahip butonu bul"""
        result = [None]
        
        def enum_child(hwnd, param):
            try:
                class_name = win32gui.GetClassName(hwnd)
                if class_name == "Button":
                    text = win32gui.GetWindowText(hwnd)
                    for t in texts:
                        if t.lower() in text.lower():
                            result[0] = hwnd
                            return False  # Aramayı durdur
            except Exception:
                pass
            return True
        
        try:
            win32gui.EnumChildWindows(parent_hwnd, enum_child, None)
        except Exception:
            pass
        
        return result[0]
    
    def _click_button(self, btn_hwnd):
        """Butona tıkla - birden fazla yöntem dene"""
        try:
            # Yöntem 1: BM_CLICK mesajı
            win32gui.SendMessage(btn_hwnd, win32con.BM_CLICK, 0, 0)
        except Exception:
            pass
        
        try:
            # Yöntem 2: Mouse tıklaması simülasyonu
            win32gui.SendMessage(btn_hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, 0)
            time.sleep(0.05)
            win32gui.SendMessage(btn_hwnd, win32con.WM_LBUTTONUP, 0, 0)
        except Exception:
            pass
    
    def _check_and_close_dialogs(self):
        """PDM dialoglarını kontrol et ve varsa iptal et"""
        def enum_windows(hwnd, param):
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                
                title = win32gui.GetWindowText(hwnd)
                if not title:
                    return True
                
                # PDM dialog başlığı mı kontrol et
                for dialog_title in self._dialog_titles:
                    if dialog_title.lower() in title.lower():
                        # Kasadan almak istiyor musunuz? sorusu içeren dialog
                        # İptal/Hayır butonunu bul
                        cancel_btn = self._find_button_by_text(hwnd, self._cancel_texts)
                        if cancel_btn:
                            # Butona tıkla
                            self._click_button(cancel_btn)
                            print(f"PDM Dialog kapatıldı (Hayır/İptal): {title}", flush=True)
                        else:
                            # Buton bulunamazsa ESC tuşu gönder
                            win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
                            win32gui.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0)
                            print(f"PDM Dialog ESC ile kapatılmaya çalışıldı: {title}", flush=True)
                        break
            except Exception:
                pass
            return True
        
        try:
            win32gui.EnumWindows(enum_windows, None)
        except Exception:
            pass
    
    def _watch_loop(self):
        """Ana izleme döngüsü"""
        while self._running:
            self._check_and_close_dialogs()
            time.sleep(0.5)  # Her 500ms'de bir kontrol et
    
    def start(self):
        """İzleyiciyi başlat"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        print("PDM Dialog izleyici başlatıldı", flush=True)
    
    def stop(self):
        """İzleyiciyi durdur"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        print("PDM Dialog izleyici durduruldu", flush=True)

# Global PDM dialog izleyici instance
_pdm_dialog_watcher = None

def start_pdm_dialog_watcher():
    """PDM dialog izleyicisini başlat"""
    global _pdm_dialog_watcher
    if _pdm_dialog_watcher is None:
        _pdm_dialog_watcher = PDMDialogWatcher()
    _pdm_dialog_watcher.start()

def stop_pdm_dialog_watcher():
    """PDM dialog izleyicisini durdur"""
    global _pdm_dialog_watcher
    if _pdm_dialog_watcher:
        _pdm_dialog_watcher.stop()

# --- Yardımcı Fonksiyonlar ---

def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def resource_path(relative_path: str) -> str:
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def read_vault_path_registry():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH) as key:
            val, _ = winreg.QueryValueEx(key, REG_VALUE_NAME)
            return val or ""
    except FileNotFoundError:
        return ""
    except Exception:
        return ""

def write_vault_path_registry(path):
    try:
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_PATH)
        winreg.SetValueEx(key, REG_VALUE_NAME, 0, winreg.REG_SZ, path or "")
    except Exception:
        pass

def check_internet_connection(host="8.8.8.8", port=53, timeout=3):
    """Check if internet connection is available."""
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except Exception:
        return False

def to_short_path(path):
    """Return Windows short (8.3) path if available; helps with long/unicode paths in COM."""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        res = ctypes.windll.kernel32.GetShortPathNameW(path, buf, len(buf))
        if res:
            return buf.value or path
    except Exception:
        pass
    return path

def to_long_path(path):
    """
    Return a long-path-safe version of the path.
    Only adds \\\\?\\ prefix when path is actually long (>240 chars) to avoid breaking COM compatibility.
    """
    if not path:
        return path
    try:
        # First normalize the path
        norm = os.path.normpath(os.path.abspath(path))
        
        # If already has prefix, return as-is
        if norm.startswith("\\\\?\\"):
            return norm
        
        # Only add prefix if path is actually long enough to need it
        # We use a conservative threshold to avoid unnecessary prefixing
        if len(norm) >= 240:
            # Handle UNC paths
            if norm.startswith("\\\\"):
                return "\\\\?\\UNC\\" + norm[2:]
            else:
                return "\\\\?\\" + norm
        
        # For shorter paths, return normalized path without prefix
        return norm
    except Exception:
        # If anything fails, return original path
        return path

def normalize_path_for_compare(path):
    """Normalize paths for comparisons; strips \\\\?\\ prefix and normalizes casing/separators."""
    try:
        if not path:
            return ""
        path = path.replace("\\\\?\\UNC\\", "\\\\")
        if path.startswith("\\\\?\\"):
            path = path[4:]
        return os.path.normcase(os.path.normpath(path))
    except Exception:
        return path or ""

def get_last_version(file_path, vault_name=VAULT_NAME):
    """Return latest version number of a PDM file; None if unavailable."""
    try:
        # Ensure path is long-path safe
        file_path = to_long_path(file_path)
        try:
            vault = win32com.client.Dispatch("ConisioLib.EdmVault5")
        except Exception:
            vault = win32com.client.Dispatch("ConisioLib.EdmVault")
        if not vault.IsLoggedIn:
            vault.LoginAuto(vault_name, 0)

        res = vault.GetFileFromPath(file_path)
        file_obj = res[0] if isinstance(res, tuple) else res
        return getattr(file_obj, "LatestVersion", None)
    except Exception:
        return None





# --- Ana Uygulama Mantığı (SolidWorks & PDM) ---

class LogicHandler:
    def __init__(self, log_queue, status_queue, progress_queue, add_to_existing_callback, stop_on_not_found_callback, stats_queue=None):
        self.log_queue = log_queue
        self.status_queue = status_queue
        self.progress_queue = progress_queue
        self.stats_queue = stats_queue
        self.get_add_to_existing = add_to_existing_callback
        self.get_stop_on_not_found = stop_on_not_found_callback
        self.config = {}
        self.vault_path = read_vault_path_registry()
        self.is_running = False
        self.is_paused = False
        if self.stats_queue is None:
            self.log("CRITICAL: Stats Queue is None!", "#ef4444")
        else:
            # self.log("Stats Queue connected.", "#2cc985")
            pass
        self.current_status = "Hazır"
        self.stats = {"total": 0, "success": 0, "error": 0}

    def update_stats(self, total=None, success=None, error=None):
        print(f"DEBUG: update_stats called with total={total}, success={success}, error={error}", flush=True)
        if total is not None: self.stats["total"] = total
        if success is not None: self.stats["success"] = success
        if error is not None: self.stats["error"] = error
        
        # Ensure total is always sent to avoid sync issues
        if total is None and "total" in self.stats:
             # Just to be safe, we rely on the self.stats state
             pass

        if self.stats_queue:
            try:
                print(f"DEBUG: Putting stats to queue: {self.stats}", flush=True)
                self.stats_queue.put(self.stats.copy())
            except Exception as e:
                self.log(f"Stats Queue Error: {e}", "#ef4444")
                print(f"DEBUG: Stats Queue Error: {e}", flush=True)
        else:
            self.log("Stats Queue is disconnected (None)", "#ef4444")
            print("DEBUG: Stats Queue is disconnected (None)", flush=True)

    def log(self, message, color=None):
        self.log_queue.put({"message": message, "color": color, "timestamp": time.time()})

    def set_status(self, status):
        self.current_status = status
        self.status_queue.put(status)

    def set_progress(self, progress):
        self.progress_queue.put(progress)

    def set_vault_path(self, path):
        """Update selected vault path (runtime only)."""
        self.vault_path = path or ""
        write_vault_path_registry(self.vault_path)

    def stop_process(self):
        self.is_running = False
        self.is_paused = False

    def pause_process(self):
        if self.is_running:
            self.is_paused = True
            self.set_status("Duraklatıldı")

    def resume_process(self):
        if self.is_running and self.is_paused:
            self.is_paused = False
            self.set_status("Çalışıyor")

    def doc_type_safe(self, doc):
        """Safely read SolidWorks doc type; handles property vs callable."""
        if not doc:
            return None
        try:
            getter = getattr(doc, "GetType", None)
            if callable(getter):
                return getter()
            if getter is not None:
                try:
                    return int(getter)
                except Exception:
                    return None
        except Exception:
            pass
        return None

    def ensure_assembly_doc(self, sw_app, doc, locked_title=None):
        """Ensure we have an active assembly doc and return a fresh pointer."""
        # Eğer locked_title varsa, sadece o montajı döndür
        if locked_title:
            try:
                sw_app.ActivateDoc3(locked_title, False, 0, None)
                active = sw_app.IActiveDoc2
                if active and self.doc_type_safe(active) == SW_DOC_ASSEMBLY:
                    try:
                        if active.GetTitle() == locked_title:
                            return active
                    except:
                        pass
            except:
                pass
            return doc  # Locked montaj bulunamazsa mevcut doc'u döndür
        
        # Normal akış (locked_title yoksa)
        try:
            if doc:
                try:
                    title = doc.GetTitle()
                except Exception:
                    title = ""
                if title:
                    try:
                        sw_app.ActivateDoc3(title, False, 0, None)
                    except Exception:
                        pass
            active = None
            try:
                active = sw_app.IActiveDoc2
            except Exception:
                active = None
            if active and self.doc_type_safe(active) == SW_DOC_ASSEMBLY:
                return active
        except Exception:
            pass
        try:
            fallback = self.get_active_assembly(sw_app)
            if fallback:
                return fallback
        except Exception:
            pass
        return doc

    def get_pdm_vault(self):
        try:
            try:
                vault = win32com.client.Dispatch("ConisioLib.EdmVault5")
            except Exception:
                vault = win32com.client.Dispatch("ConisioLib.EdmVault")
            if not vault.IsLoggedIn:
                vault.LoginAuto(VAULT_NAME, 0)
            return vault
        except Exception as e:
            err_str = str(e)
            # Simplify error messages
            if "Geçersiz sınıf dizesi" in err_str or "-2147221005" in err_str:
                self.log("PDM istemcisi kurulu değil veya çalışmıyor.", "#ef4444")
            elif "Arşiv sunucusu bulunamadı" in err_str:
                self.log("PDM sunucusuna bağlanılamıyor. Sunucu kapalı olabilir.", "#ef4444")
            elif "LoginAuto" in err_str or "IsLoggedIn" in err_str:
                self.log("PDM oturum açılamadı. Giriş bilgilerini kontrol edin.", "#ef4444")
            else:
                self.log("PDM bağlantı hatası.", "#ef4444")
            return None

    def get_sw_app(self):
        try:
            sw_app = win32com.client.GetActiveObject("SldWorks.Application")
            self.log("Mevcut SolidWorks oturumu bulundu.", "#10b981")
            return sw_app
        except Exception:
            self.log("Açık SolidWorks oturumu bulunamadı, başlatılıyor...", "#f59e0b")
        
        try:
            sw_app = win32com.client.Dispatch("SldWorks.Application")
            sw_app.Visible = True
            return sw_app
        except Exception as e:
            self.log(f"SolidWorks başlatılamadı. Lütfen kurulu olduğundan emin olun: {e}", "#ef4444")
            return None

    def get_active_assembly(self, sw_app):
        """Açık montaj dokümanana döndür; aktif yoksa açık belgelerden bul."""
        candidates = []
        try:
            doc = getattr(sw_app, "IActiveDoc2", None)
            if doc:
                candidates.append(doc)
        except Exception:
            pass
        try:
            doc = getattr(sw_app, "ActiveDoc", None)
            if doc:
                candidates.append(doc)
        except Exception:
            pass
        for doc in candidates:
            try:
                if doc and self.doc_type_safe(doc) == SW_DOC_ASSEMBLY:
                    return doc
            except Exception:
                continue
        try:
            names = sw_app.GetOpenDocumentNames() or []
            for name in names:
                try:
                    doc = sw_app.ActivateDoc3(name, False, 0, None)
                    if doc and self.doc_type_safe(doc) == SW_DOC_ASSEMBLY:
                        return doc
                except Exception:
                    continue
        except Exception:
            pass
        return None


    def map_vault_path(self, vault, pdm_path):
        """PDM yolunu kullanıcının seçtiği kasa yoluna göre dönüştürür."""
        if not pdm_path or not self.vault_path:
            return pdm_path
        try:
            root = getattr(vault, "RootFolderPath", "") or ""
            root_norm = os.path.normpath(root) if root else ""
            pdm_norm = os.path.normpath(pdm_path)
            if root_norm:
                try:
                    if os.path.commonpath([pdm_norm, root_norm]) == root_norm:
                        rel = os.path.relpath(pdm_norm, root_norm)
                        return os.path.normpath(os.path.join(self.vault_path, rel))
                except Exception:
                    pass
        except Exception:
            return pdm_path
        return pdm_path

    def build_path_candidates(self, path):
        """Return unique path variants (long/short/original) plus normalized compare set."""
        short_path = to_short_path(path)
        long_path = to_long_path(path)
        candidates = []
        for p in (long_path, short_path, path):
            if p and p not in candidates:
                candidates.append(p)
        compare_set = {normalize_path_for_compare(p) for p in candidates if p}
        return candidates, compare_set

    def search_file_in_pdm(self, vault, sap_code):
        if not self.is_running: return None
        
        sap_code = str(sap_code).strip()
        
        # 1. Variable Search
        for var_name in PDM_VAR_NAMES:
            try:
                search = vault.CreateSearch()
                search.AddVariable(var_name, sap_code)
                result = search.GetFirstResult()
                while result:
                    if not self.is_running: return None
                    if self.check_file_match(vault, result.ID, sap_code):
                        self.log(f"  PDM'de bulundu ({var_name}): {result.Name}", "#0ea5e9")
                        return self.map_vault_path(vault, result.Path)
                    result = search.GetNextResult()
            except Exception:
                pass
                
        # 2. Filename Search (Fallback)
        try:
            search = vault.CreateSearch()
            search.FileName = f"%{sap_code}%"
            result = search.GetFirstResult()
            while result:
                if not self.is_running: return None
                if self.check_file_match(vault, result.ID, sap_code):
                    self.log(f"  PDM'de bulundu (Dosya Adı): {result.Name}", "#0ea5e9")
                    return self.map_vault_path(vault, result.Path)
                result = search.GetNextResult()
        except Exception:
            pass
            
        return None

    def check_file_match(self, vault, file_id, target_code):
        """Verifies if the file actually matches the target SAP code."""
        try:
            # EdmObjectType.EdmObject_File = 1
            file_obj = vault.GetObject(1, file_id)
            if not file_obj: return False
            
            ext = os.path.splitext(file_obj.Name)[1].lower()
            if ext not in PREFERRED_EXTS: return False
            
            enum_var = file_obj.GetEnumeratorVariable()
            if not enum_var: return False
            
            target_str = str(target_code).strip()
            
            for var_name in PDM_VAR_NAMES:
                # Check "@" configuration
                try:
                    # win32com handles 'out' parameters by returning them
                    # GetVar returns (boolean_success, value) or just value depending on wrapper
                    # But usually with Dispatch, we just call it and catch exceptions if it fails
                    # Let's try to get the value. 
                    # Note: In Python win32com, some methods return the value directly, others return tuple.
                    # PDM API GetVar signature: GetVar(VarName, ConfigName, out Value)
                    val = enum_var.GetVar(var_name, "@")
                    
                    # Ensure val is the value, sometimes it returns (True, Value)
                    if isinstance(val, tuple) and len(val) > 0:
                         # Usually (True, 'Value')
                         real_val = val[1] if len(val) > 1 else val[0]
                    else:
                        real_val = val

                    if real_val is not None and str(real_val).strip() == target_str:
                        return True
                except Exception:
                    pass
                    
            return False
        except Exception:
            return False

    def fetch_latest_revision(self, vault, file_path):
        """
        fetch_pdm_latest.py mantığını kullanarak dosyanın son revizyonunu çeker.
        Dosya yerelde yoksa veya eski sürümse günceller.
        """
        # Ensure path is long-path safe
        file_path = to_long_path(file_path)
        file_name = os.path.basename(file_path)
        
        try:
            # GetFileFromPath ile dosya ve klasör nesnelerini al
            result = vault.GetFileFromPath(file_path, None)
            
            if isinstance(result, tuple) and len(result) >= 2:
                file_obj = result[0]
                folder_obj = result[1]
            else:
                file_obj = result
                folder_obj = None
            
            if not file_obj:
                self.log(f"  PDM'de dosya bulunamadı: {file_name}", "#ef4444")
                return False
            
            # Folder object yoksa parent folder'ı al
            if not folder_obj:
                try:
                    folder_obj = file_obj.GetParentFolder()
                except Exception:
                    pass
            
            if not folder_obj:
                self.log(f"  Dosya klasör bilgisi alınamadı: {file_name}", "#ef4444")
                return False
            
            # Montaj dosyası ise referanslarıyla birlikte çek (BatchGet)
            is_assembly = file_path.lower().endswith(".sldasm")
            
            # Sürüm kontrolü ve loglama
            try:
                local_version = file_obj.GetLocalVersionNo(folder_obj.ID)
                latest_version = file_obj.CurrentVersion
                
                # Montaj değilse ve sürüm güncelse atla
                if not is_assembly and os.path.exists(file_path) and local_version >= latest_version:
                    self.log(f"  Dosya güncel (v{local_version}): {file_name}", "#0ea5e9")
                    return True
                
                # Montaj ise her durumda kontrol et/güncelle (referanslar için)
                if is_assembly:
                     self.log(f"  Montaj referansları kontrol ediliyor...: {file_name}", "#3b82f6")
                else:
                    self.log(f"  Sürüm güncelleniyor (v{local_version} -> v{latest_version}): {file_name}", "#3b82f6")
            except Exception as ver_err:
                self.log(f"  Sürüm bilgisi alınamadı, son sürüm çekiliyor: {file_name}", "#f59e0b")
            
            # GetFileCopy veya BatchGet (Montajlar için)
            try:
                if is_assembly:
                    # Montajlar için BatchGet kullan (Referansları da çeker)
                    batch_getter = vault.CreateUtility(12) # EdmUtil_BatchGet
                    batch_getter.AddSelection(file_obj, 0)
                    # CreateTree flags: Egcf_GetLatestRevision | Egcf_GetReferences (Default implied usually but let's be sure)
                    # 65536 = Egcf_GetLatestRevision
                    batch_getter.CreateTree(0, 65536) 
                    batch_getter.GetFiles(0, None)
                else:
                    # Parçalar için hızlı GetFileCopy
                    file_obj.GetFileCopy(
                        0,                          # parent window handle (none)
                        0,                          # version number (0 = latest)
                        folder_obj.ID,              # folder reference
                        EGCF_GET_LATEST_REVISION,   # flag: en son revizyonu çek
                        "",                         # destination path (boş = varsayılan)
                    )
            except Exception as copy_err:
                # Alternatif yöntem dene
                try:
                    file_obj.GetFileCopy(0, 0, folder_obj.ID, 0, "")
                except Exception as alt_err:
                    self.log(f"  Dosya kopyalama hatası: {alt_err}", "#ef4444")
                    return False
            
            # Dosyanın indirilmesini bekle
            for attempt in range(30):  # 7.5 saniye maksimum
                if os.path.exists(file_path):
                    # Dosya boyutunu kontrol et (indirme tamamlandı mı?)
                    try:
                        size = os.path.getsize(file_path)
                        if size > 0:
                            self.log(f"  Son sürüm indirildi: {file_name}", "#10b981")
                            return True
                    except Exception:
                        pass
                time.sleep(0.25)
            
            # Son kontrol
            if os.path.exists(file_path):
                self.log(f"  Dosya indirildi: {file_name}", "#10b981")
                return True
            
            self.log(f"  Dosya indirme zaman aşımına uğradı: {file_name}", "#ef4444")
            return False
            
        except Exception as e:
            self.log(f"  Son sürüm çekilirken hata oluştu: {e}", "#ef4444")
            return False

    def ensure_local_file(self, vault, file_path):
        """
        Dosyanın yerelde olduğundan ve güncel olduğundan emin ol.
        Yoksa veya eskiyse PDM'den son sürümü çek.
        """
        # Ensure path is long-path safe
        file_path = to_long_path(file_path)
        file_name = os.path.basename(file_path)
        
        # Önce dosyanın durumunu kontrol et
        file_exists = os.path.exists(file_path)
        
        if file_exists:
            # Dosya var, sürüm kontrolü yap
            try:
                result = vault.GetFileFromPath(file_path, None)
                if isinstance(result, tuple) and len(result) >= 2:
                    file_obj = result[0]
                    folder_obj = result[1]
                else:
                    file_obj = result
                    folder_obj = None
                
                if not folder_obj and file_obj:
                    try:
                        folder_obj = file_obj.GetParentFolder()
                    except Exception:
                        folder_obj = None
                
                if file_obj and folder_obj:
                    local_version = file_obj.GetLocalVersionNo(folder_obj.ID)
                    latest_version = file_obj.CurrentVersion
                    
                    if local_version >= latest_version:
                        self.log(f"  Dosya güncel (v{local_version}): {file_name}", "#0ea5e9")
                        return True
                    else:
                        self.log(f"  Güncelleme gerekli (v{local_version} v{latest_version}): {file_name}", "#f59e0b")
            except Exception as ver_check_err:
                # Sürüm kontrolü başarısız, yine de güncellemeyi dene
                self.log(f"  Sürüm kontrolü yapılamadı, güncelleniyor: {file_name}", "#f59e0b")
        else:
            self.log(f"  Dosya yerelde yok, indiriliyor: {file_name}", "#f59e0b")
        
        # fetch_pdm_latest.py mantığını kullanarak son sürümü çek
        return self.fetch_latest_revision(vault, file_path)

    def get_assembly_template(self, sw_app):
        # Eğer özel bir yol belirtilmemişse SolidWorks ayarlarına bak
        if not TEMPLATE_OVERRIDE:
            try:
                # DİKKAT: Burası 8 değil 9 olmalı.
                # 8 -> Parça (Part), 9 -> Montaj (Assembly)
                return sw_app.GetUserPreferenceStringValue(9)
            except Exception:
                return ""
        return TEMPLATE_OVERRIDE

    def init_assembly_doc(self, sw_app):
        """
        Initialize assembly document. Returns (assembly_doc, locked_title, asm_title, pre_open_docs, z_offset).
        Extracted common assembly initialization code to follow DRY principle.
        """
        add_to_existing = self.get_add_to_existing()
        locked_title = None
        assembly_doc = None

        if add_to_existing:
            assembly_doc = self.get_active_assembly(sw_app)
            if assembly_doc:
                self.log("Mevcut montaja parçalar eklenecek.", "#10b981")
                try:
                    locked_title = assembly_doc.GetTitle() or ""
                except Exception:
                    locked_title = ""
            else:
                self.log("Açık montaj bulunamadı, yeni montaj oluşturulacak.", "#f59e0b")
                add_to_existing = False

        if not add_to_existing:

            
            template = self.get_assembly_template(sw_app)
            new_doc = sw_app.NewDocument(template, SW_DOC_ASSEMBLY, 0, 0)
            if not new_doc:
                self.log("Montaj oluşturulamadı.", "#ef4444")
                return None, None, None, None, 0.0
            assembly_doc = new_doc
            try:
                locked_title = assembly_doc.GetTitle() or ""
                self.log(f"Yeni montaj kilitlendi: {locked_title}", "#3b82f6")
            except Exception:
                locked_title = ""

        assembly_doc = self.ensure_assembly_doc(sw_app, assembly_doc)
        if not assembly_doc or self.doc_type_safe(assembly_doc) != SW_DOC_ASSEMBLY:
            self.log("Aktif montaj alınamadı.", "#ef4444")
            return None, None, None, None, 0.0

        try:
            asm_title = assembly_doc.GetTitle()
            if asm_title:
                sw_app.ActivateDoc3(asm_title, False, 0, None)
        except Exception:
            asm_title = ""

        try:
            pre_open_docs = set(sw_app.GetOpenDocumentNames() or [])
        except Exception:
            pre_open_docs = set()

        # Calculate initial z_offset
        offset_step = -0.3
        z_offset = 0.0
        if self.get_add_to_existing():
            existing_count = 0
            try:
                comps_before = assembly_doc.GetComponents(True) or []
                existing_count = len(comps_before)
            except Exception:
                pass
            z_offset = existing_count * offset_step
            if existing_count == 0:
                self.log(f"Montaj boş, yeni parçalar Z=0m'den başlayacak", "#3b82f6")
            else:
                self.log(f"Montajda {existing_count} parça var, yeni parçalar Z={z_offset:.3f}m'den başlayacak", "#3b82f6")

        return assembly_doc, locked_title, asm_title, pre_open_docs, z_offset

    def add_component_to_assembly(self, sw_app, assembly_doc, file_path, z_offset, asm_title, pre_open_docs):
        """
        Adds a component to the assembly. Returns (success, new_z_offset).
        Extracted common code from batch and immediate modes to follow DRY principle.
        """
        
        # Ensure path is long-path safe
        file_path = to_long_path(file_path)

        if not os.path.exists(file_path):
            if not self.ensure_local_file(self.get_pdm_vault(), file_path) or not os.path.exists(file_path):
                self.log(f"Yerel kopya eksik: {file_path}", "#ef4444")
                return False, z_offset

        path_candidates, target_paths = self.build_path_candidates(file_path)

        comp = None
        errors = []
        comp_doc = None
        try:
            existing_names = {getattr(c, "Name2", "") for c in (assembly_doc.GetComponents(True) or []) if c}
        except Exception:
            existing_names = set()

        ext = os.path.splitext(file_path)[1].lower()
        doc_type = SW_DOC_PART if ext == ".sldprt" else SW_DOC_ASSEMBLY if ext == ".sldasm" else 0

        config_name = ""
        if doc_type:
            for candidate in path_candidates:
                comp_doc, _ = self.open_component_doc(sw_app, candidate, doc_type)
                if comp_doc:
                    break
            try:
                cfgs = comp_doc.GetConfigurationNames() if comp_doc else None
                if cfgs:
                    config_name = list(cfgs)[0]
            except Exception:
                config_name = ""

        math_util = None
        try:
            math_util = sw_app.GetMathUtility()
        except Exception:
            math_util = None

        transform = None
        if math_util:
            try:
                t = (1.0, 0.0, 0.0,
                     0.0, 1.0, 0.0,
                     0.0, 0.0, 1.0,
                     0.0, 0.0, z_offset)
                transform = math_util.CreateTransform(t)
            except Exception as ex:
                errors.append(f"Transform: {ex}")

        def attempt(label, fn):
            nonlocal comp
            if comp:
                return
            for candidate in path_candidates:
                if comp:
                    return
                try:
                    comp = fn(candidate)
                    if comp:
                        return
                except Exception as ex:
                    errors.append(f"{label} ({candidate}): {ex}")

        attempt("InsertExistingComponent3", lambda p: assembly_doc.InsertExistingComponent3(p, transform, False) if transform else None)
        attempt("AddComponent6", lambda p: assembly_doc.AddComponent6(p, 1, config_name or "", transform, False, 0) if transform else None)
        attempt("AddComponent5-0", lambda p: assembly_doc.AddComponent5(p, 0, config_name or "", 0, 0, z_offset))
        attempt("AddComponent5-1", lambda p: assembly_doc.AddComponent5(p, 1, config_name or "", 0, 0, z_offset))
        attempt("AddComponent5-2", lambda p: assembly_doc.AddComponent5(p, 2, config_name or "", 0, 0, z_offset))
        attempt("InsertExistingComponent2", lambda p: assembly_doc.InsertExistingComponent2(p, 0, 0, z_offset))
        attempt("AddComponent4", lambda p: assembly_doc.AddComponent4(p, 0, 0, z_offset))
        attempt("AddComponent", lambda p: assembly_doc.AddComponent(p, 0, 0, z_offset))

        if not comp:
            try:
                comps_after = assembly_doc.GetComponents(True) or []
                for c in comps_after:
                    name = getattr(c, "Name2", "")
                    comp_path = ""
                    try:
                        comp_path = c.GetPathName() or ""
                    except Exception:
                        try:
                            comp_path = c.GetPathName2() or ""
                        except Exception:
                            comp_path = ""
                    if comp_path and normalize_path_for_compare(comp_path) in target_paths:
                        comp = c
                        break
                    if name and name not in existing_names:
                        comp = c
                        break
            except Exception:
                pass

        success = False
        new_z_offset = z_offset
        if comp:
            # Wait for component to be fully added
            time.sleep(0.3)
            
            # Float logic removed as per request

            
            # Float logic removed as per request


            self.log(f"Eklendi: {os.path.basename(file_path)} (Z={z_offset:.3f}m)", "#10b981")
            new_z_offset = z_offset - 0.3  # offset_step
            success = True
        else:
            # Check if this is a COM disconnection error (needs restart)
            error_str = ' '.join(errors) if errors else ''
            is_connection_error = ('istemcilerinden ayrılmış' in error_str or 
                                   '-2147417848' in error_str or 
                                   '<unknown>' in error_str)
            
            if is_connection_error:
                self.log(f"Eklenemedi: {os.path.basename(file_path)} (bağlantı hatası)", "#ef4444")
                # Signal that SW needs restart by returning special value
                return False, z_offset, True  # Third value = needs_restart
            else:
                self.log(f"Eklenemedi: {os.path.basename(file_path)}", "#f59e0b")

        # Close component document
        try:
            assembly_title = asm_title or ""
            if comp_doc:
                comp_title = ""
                try:
                    comp_title = comp_doc.GetTitle()
                except Exception:
                    comp_title = ""
                if comp_title and comp_title != assembly_title:
                    try:
                        sw_app.CloseDoc(comp_title)
                    except Exception:
                        pass

            close_candidates = set()
            base_title = os.path.basename(file_path)
            if base_title:
                close_candidates.add(base_title)
            try:
                current_docs = set(sw_app.GetOpenDocumentNames() or [])
                for name in current_docs:
                    if name and name not in pre_open_docs and name != assembly_title:
                        close_candidates.add(name)
            except Exception:
                pass

            for name in close_candidates:
                if name and name != assembly_title:
                    try:
                        sw_app.CloseDoc(name)
                    except Exception:
                        pass
        except Exception:
            pass

        return success, new_z_offset, False  # Third value = needs_restart

    def apply_cleanup_logic(self, sw_app, assembly_doc):
        """
        Applies UnFix and Solving=1 logic to all components.
        Silent operation (no logs) as requested.
        """
        try:
            # Kullanıcının isteği üzerine bağlantıyı tazeliyoruz
            try:
                swApp = win32com.client.GetActiveObject("SldWorks.Application")
                assembly_doc = swApp.ActiveDoc
            except:
                pass

            if not assembly_doc:
                return
            
            # --- Kullanıcının çalışan kodunun entegrasyonu ---
            try:
                # 1. Montaj İsmini Al
                try:
                    full_title = assembly_doc.GetTitle 
                except:
                    full_title = assembly_doc.GetTitle() # Fallback

                montaj_ismi = full_title.split('.')[0]
                
                # 2. Bileşen Listesini Al
                configMgr = assembly_doc.ConfigurationManager
                config = configMgr.ActiveConfiguration
                root_comp = config.GetRootComponent3(True)
                v_components = root_comp.GetChildren

                if v_components:
                    for comp in v_components:
                        try:
                            parca_ismi = comp.Name2
                            tam_isim = f"{parca_ismi}@{montaj_ismi}"
                            
                            # --- ADIM 1: FIX KALDIRMA ---
                            boolstatus = assembly_doc.Extension.SelectByID2(tam_isim, "COMPONENT", 0, 0, 0, False, 0, pythoncom.Nothing, 0)
                            
                            if boolstatus:
                                try:
                                    assembly_doc.UnFixComponent()
                                except:
                                    pass
                                assembly_doc.ClearSelection2(True)
                            
                            # --- ADIM 2: ESNEK YAPMA ---
                            boolstatus = assembly_doc.Extension.SelectByID2(tam_isim, "COMPONENT", 0, 0, 0, False, 0, pythoncom.Nothing, 0)
                            
                            if boolstatus:
                                selMgr = assembly_doc.SelectionManager
                                myComponent = selMgr.GetSelectedObjectsComponent3(1, 0)
                                
                                if myComponent:
                                    try:
                                        myComponent.Solving = 1
                                    except:
                                        pass
                                    
                                assembly_doc.ClearSelection2(True)

                        except:
                            pass

                    try:
                        assembly_doc.GraphicsRedraw2()
                    except:
                        pass
                    
                    # Kullanıcı isteği: İzometrik Görünüm + Zoom to Fit
                    try:
                        # "*Isometric" (English) - Standart ID 7
                        assembly_doc.ShowNamedView2("*Isometric", 7)
                        # "*İzometrik" (Turkish) - eğer dil farklıysa garanti olsun diye
                        assembly_doc.ShowNamedView2("*İzometrik", 7)
                        
                        assembly_doc.ViewZoomtofit2()
                    except:
                        pass
            except:
                pass
                
        except Exception:
            pass

    def open_component_doc(self, sw_app, file_path, doc_type):
        """Open component and let PDM add-in retrieve it if needed"""
        if doc_type == 0:
            return None, False
        try:
            try:
                before = set(sw_app.GetOpenDocumentNames() or [])
            except Exception:
                before = set()
            try:
                status = win32com.client.VARIANT(pythoncom.VT_I4, 0)
                warnings = win32com.client.VARIANT(pythoncom.VT_I4, 0)
            except Exception:
                status = 0
                warnings = 0
            try:
                # Use 0 instead of SW_OPEN_SILENT - PDM add-in needs to retrieve file
                doc = sw_app.OpenDoc6(file_path, doc_type, 0, "", status, warnings)
                
                # Wait for PDM to retrieve file
                if doc:
                    time.sleep(1.5)  # Give PDM time to check out/get file
                    
                    # Verify file is now local
                    if not os.path.exists(file_path):
                        self.log(f"  ⚠ Dosya açıldı ancak yerel diskte bulunamadı: {os.path.basename(file_path)}", "#f59e0b")
                    else:
                        self.log(f"  ✔ Dosya başarıyla yerel diske çekildi: {os.path.basename(file_path)}", "#6b7280")
            except Exception:
                doc = sw_app.OpenDoc(file_path, doc_type)
                time.sleep(1.5)
            
            opened_now = False
            try:
                title = doc.GetTitle() if doc else ""
                opened_now = bool(title and title not in before)
            except Exception:
                opened_now = False
            return doc, opened_now
        except Exception as e:
            self.log(f"  Bileşen açılırken hata oluştu: {str(e)}", "#6b7280")
            return None, False


    def run_process(self, codes, config=None):
        pythoncom.CoInitialize()
        self.is_running = True
        
        # Check for Multi-Kit SAP Mode
        if config and config.get('multiKitMode'):
             self.run_process_sap_multikit(codes, config)
             pythoncom.CoUninitialize()
             return
        
        # PDM dialog izleyicisini başlat (Kasadan Al dialoglarını otomatik iptal eder)
        start_pdm_dialog_watcher()

        # Clean and validate codes
        cleaned_codes = []
        for c in codes:
            c = c.strip()
            if not c: continue
            # Ignore likely row numbers (e.g., "1", "10") or list markers (e.g., "1.")
            if (c.isdigit() and len(c) < 3) or (c.endswith(".") and c[:-1].isdigit() and len(c) < 4):
                self.log(f"  ⚠ '{c}' geçersiz kod/sıra no olarak algılandı ve atlandı.", "#f59e0b")
                continue
            cleaned_codes.append(c)
        
        codes = cleaned_codes

        if not codes:
            self.log("İşlenecek geçerli kod bulunamadı.", "#ef4444")
            self.set_status("Durduruldu")
            self.is_running = False
            stop_pdm_dialog_watcher()
            pythoncom.CoUninitialize()
            return

        try:
            self.set_progress(0.1)
            self.set_status("PDM'e bağlanılıyor...")
            
            # Retry PDM connection every 1 minute until successful
            retry_count = 0
            vault = None
            while self.is_running:
                vault = self.get_pdm_vault()
                if vault:
                    break
                
                retry_count += 1
                self.log(f"PDM bağlantısı sağlanamadı. 1 dakika bekleniyor... (deneme #{retry_count})", "#f59e0b")
                
                # Wait 60 seconds, but check is_running every second
                for _ in range(60):
                    if not self.is_running:
                        return
                    time.sleep(1)
            
            if not vault:
                self.set_status("Hata")
                self.log("PDM bağlantısı sağlanamadı. İşlem durduruldu.", "#ef4444")
                return
            
            if retry_count > 0:
                self.log("PDM bağlantısı sağlandı! Devam ediliyor...", "#10b981")

            # Checkbox durumuna göre farklı iş akışları
            stop_on_not_found = self.get_stop_on_not_found()
            
            if stop_on_not_found:
                # ESKİ AKIŞ: Önce tüm parçaları ara, sonra montaja ekle
                self.run_process_batch_mode(codes, vault)
            else:
                # YENİ AKIŞ: Bulundu -> Hemen ekle
                self.run_process_immediate_mode(codes, vault)

        except Exception as e:
            self.log(f"Beklenmedik Hata: {e}", "#ef4444")
            self.set_status("Hata")
        finally:
            if self.is_running:
                 self.log("İşlem sonlandırılıyor...", "#64748b")
            
            self.is_running = False
            
            # Son bir temizlik ve olası hata pencerelerini yakalamak için kısa bir bekleme
            time.sleep(3)
            
            # PDM dialog izleyicisini durdur
            stop_pdm_dialog_watcher()
            
            # Eğer işlem bittiğinde statü hala aktif bir durumdaysa, Durduruldu olarak işaretle
            final_statuses = ["Tamamlandı", "Hata", "İptal", "Durduruldu"]
            if self.current_status not in final_statuses:
                self.set_status("Durduruldu")

            vault = None
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
    
    def run_process_sap_multikit(self, codes, config):
        """SAP üzerinden Çoklu Kit Montajı akışını yönetir."""
        self.set_status("SAP Başlatılıyor...")
        
        # PDM dialog izleyicisini başlat
        start_pdm_dialog_watcher()
        
        try:
            # SapGui init moved to loop
            
            # PDM Bağlantısı Kur (Ön Hazırlık)
            self.set_status("PDM'e bağlanılıyor...")
            vault = None
            retry_count = 0
            
            while self.is_running:
                vault = self.get_pdm_vault()
                if vault: break
                retry_count += 1
                if retry_count > 3: # SAP modunda çok beklemeyelim, 3 deneme yeterli
                    self.log("PDM bağlantısı sağlanamadı. SAP işlemi iptal edildi.", "#ef4444")
                    self.set_status("Hata")
                    return
                time.sleep(1)
                
            if not vault:
                self.set_status("Hata")
                return

            self.set_status("Kitler İşleniyor...")
            total = len(codes)
            stop_on_not_found = self.get_stop_on_not_found()

            self.set_status("Kitler İşleniyor...")
            total = len(codes)
            stop_on_not_found = self.get_stop_on_not_found()
            
            for i, code in enumerate(codes):
                if not self.is_running:
                    self.log("İşlem kullanıcı tarafından durduruldu.", "#ef4444")
                    break
                
                code = code.strip()
                if not code: continue
                
                self.log(f"[{i+1}/{total}] Kit İşleniyor: {code}", "#3b82f6")
                self.set_status(f"SAP Okunuyor: {code}")
                
                # CS03'ten verileri çek (Isolated SAP Instance)
                result = None
                try:
                    sap = SapGui()
                    if sap.connect_to_sap():
                        # Login is fast if session exists
                        uname = config.get('sapUsername', '')
                        pwd = config.get('sapPassword', '')
                        if uname and pwd:
                             sap.sapLogin(uname, pwd)
                        
                        result = sap.get_bom_components(code)
                    else:
                        self.log("SAP bağlantısı kurulamadı.", "#ef4444")
                except Exception as e:
                    self.log(f"SAP işlem hatası: {str(e)}", "#ef4444")
                
                # Release SAP COM object before PDM/SW operations
                try:
                    if 'sap' in locals(): del sap
                except: pass
                
                header_info = None
                components = []

                if isinstance(result, dict):
                    components = result.get('components', [])
                    header_info = result.get('header')
                else:
                    components = result

                if components:
                    self.log(f"{len(components)} bileşen bulundu.", "#10b981")
                    
                    # Tablo Logu (Mavi) - Başlıklı Format
                    log_buffer = []
                    
                    if header_info and header_info.get('material'):
                        log_buffer.append(f"KİT KODU: {header_info['material']}  |  KİT TANIMI: {header_info['description']}")
                        log_buffer.append("=" * 68)

                    log_buffer.append(f"{'NO':<2} | {'BİLEŞEN':<9} | {'TANIM':<40} | {'MİKTAR'}")
                    log_buffer.append("-" * 68)
                    
                    for idx, comp in enumerate(components):
                        row_num = idx + 1
                        desc = comp['description']
                        if len(desc) > 40:
                            desc = desc[:40] + "..."
                        line = f"{row_num:<2} | {comp['code']:<9} | {desc:<40} | {comp['quantity']}"
                        log_buffer.append(line)
                    
                    full_log = "\n".join(log_buffer)
                    self.log(full_log, "#3b82f6")
                    
                    # MONTAJ İŞLEMİNİ BAŞLAT
                    self.log(f"Montaj başlatılıyor: {code} (Parça Sayısı: {len(components)})", "#6366f1")
                    raw_child_codes = [c['code'].strip() for c in components if c.get('code') and c['code'].strip()]
                    
                    # Clean and validate codes (Simulate manual input processing)
                    child_codes = []
                    for c in raw_child_codes:
                        if not c: continue
                        # Ignore likely row numbers (e.g., "1", "10") or list markers (e.g., "1.")
                        if (c.isdigit() and len(c) < 3) or (c.endswith(".") and c[:-1].isdigit() and len(c) < 4):
                            self.log(f"  Atlandı: '{c}' (Geçersiz format)", "#f59e0b")
                            continue
                        child_codes.append(c)
                    
                    if not child_codes:
                         self.log("Eklenecek geçerli parça bulunamadı (Filtreleme sonrası).", "#f59e0b")
                         # continue loop but we are inside if components

                    
                    # Vault Health Check
                    try:
                        _ = vault.Name
                    except:
                        self.log("PDM Vault bağlantısı koptu, yeniden bağlanılıyor...", "#f59e0b")
                        vault = self.get_pdm_vault()
                    
                    if stop_on_not_found:
                        self.log("Batch modu başlatılıyor...", "#6366f1")
                        self.run_process_batch_mode(child_codes, vault, is_subprocess=True)
                    else:
                        self.log("Immediate modu başlatılıyor...", "#6366f1")
                        self.run_process_immediate_mode(child_codes, vault, is_subprocess=True)

                else:
                    self.log(f"Bileşen bulunamadı veya SAP hatası.", "#ef4444")
                
                self.set_progress((i + 1) / total)
                time.sleep(1) 
                
            self.set_status("Tamamlandı")
            self.is_running = False
            self.log("Tüm Kit İşlemleri Tamamlandı.", "#10b981")
            
        finally:
            stop_pdm_dialog_watcher()

    def run_process_batch_mode(self, codes, vault, is_subprocess=False):
        """ESKİ AKIŞ: Önce tüm parçaları ara, sonra montaja ekle (checkbox işaretli)"""
        if is_subprocess: self.log(f"Alt Süreç Başladı: Batch Mode ({len(codes)} parça)", "#6366f1")
        
        # Ensure Vault is valid
        try:
            _ = vault.Name
        except:
            if is_subprocess: self.log("Alt süreç için PDM bağlantısı tazeleniyor...", "#3b82f6")
            vault = self.get_pdm_vault()


        found_files = []
        not_found_codes = []

        self.set_status("Parçalar aranıyor...")
        total_codes = len(codes)
        
        # Initialize stats if not subprocess (or reset for new sub-batch)
        if not is_subprocess:
             self.update_stats(total=total_codes, success=0, error=0)
        
        for i, code in enumerate(codes):
            if not self.is_running:
                if not is_subprocess: self.log("İşlem durduruldu.", "#f97316")
                return
            
            if self.is_paused and self.is_running:
                self.log("İşlem duraklatıldı.", "#0ea5e9")
            while self.is_paused and self.is_running:
                time.sleep(0.5)
            path = self.search_file_in_pdm(vault, code)
            if not self.is_running:
                if not is_subprocess: self.log("İşlem durduruldu.", "#f97316")
                return
            if path:
                if self.ensure_local_file(vault, path):
                    found_files.append(path)
                    self.log(f"Bulundu: {code}", "#10b981")
                    # self.update_stats(success=len(found_files)) # Stats karmaşası olmasın
                else:
                    not_found_codes.append(code)
                    self.log(f"Bulunamadı: {code}", "#ef4444")
                    # self.update_stats(error=len(not_found_codes))
            else:
                not_found_codes.append(code)
                self.log(f"Bulunamadı: {code}", "#ef4444")
                # self.update_stats(error=len(not_found_codes))
            self.set_progress(0.1 + (0.4 * (i + 1) / total_codes))

        if not_found_codes:
            not_found_str = ",".join(not_found_codes)
            self.log(f"Bulunamayan SAP kodları ({len(not_found_codes)} adet): {not_found_str} PDM'de yok.", "#f59e0b")
            self.log("Bulunamayan parçalar var, montaj iptal edildi.", "#f59e0b")
            self.set_progress(1)
            self.set_status("İptal")
            return

        if not found_files:
            self.log("Eklenecek parça bulunamadı (PDM'de hiçbiri yok).", "#f59e0b")
            return

        if not self.is_running:
            return

        # SolidWorks'ü başlat ve montajı hazırla
        self.set_status("SolidWorks başlatılıyor...")
        sw_app = self.get_sw_app()
        if not sw_app:
            self.set_status("Hata")
            self.log("SolidWorks başlatılamadı. İşlem durduruldu.", "#ef4444")
            return

        assembly_doc, locked_title, asm_title, pre_open_docs, z_offset = self.init_assembly_doc(sw_app)
        if not assembly_doc:
            return

        self.set_status("Parçalar ekleniyor...")

        total_files = len(found_files)
        i = 0
        while i < total_files:
            file_path = found_files[i]
            
            if not self.is_running:
                return

            if self.is_paused and self.is_running:
                self.log("İşlem duraklatıldı.", "#0ea5e9")
            while self.is_paused and self.is_running:
                time.sleep(0.5)

            # Check if SolidWorks is still running
            sw_alive = True
            try:
                _ = sw_app.Visible
            except Exception:
                sw_alive = False
            
            if not sw_alive:
                self.log("SolidWorks kapandı! Yeniden başlatılıyor...", "#f59e0b")
                sw_app = self.get_sw_app()
                if not sw_app:
                    self.log("SolidWorks başlatılamadı.", "#ef4444")
                    self.set_status("Hata")
                    return
                assembly_doc, locked_title, asm_title, pre_open_docs, z_offset = self.init_assembly_doc(sw_app)
                if not assembly_doc:
                    return
                i = 0 # Restart adding
                continue

            if locked_title:
                try:
                    sw_app.ActivateDoc3(locked_title, False, 0, None)
                except Exception:
                    pass

            assembly_doc = self.ensure_assembly_doc(sw_app, assembly_doc)
            if not assembly_doc:
                # Re-init logic similar to above
                 self.log("Montaj bağlantısı koptu.", "#ef4444")
                 return

            result = self.add_component_to_assembly(sw_app, assembly_doc, file_path, z_offset, asm_title, pre_open_docs)
            success, z_offset, needs_restart = result[0], result[1], result[2] if len(result) > 2 else False
            
            if needs_restart:
                # Restart logic
                sw_app = self.get_sw_app()
                if sw_app:
                    assembly_doc, locked_title, asm_title, pre_open_docs, z_offset = self.init_assembly_doc(sw_app)
                    if assembly_doc:
                        i = 0
                        continue
            
            if not success and not needs_restart:
                 # Check alive logic
                 pass
            
            self.set_progress(0.5 + (0.5 * (i + 1) / total_files))
            i += 1

        self.apply_cleanup_logic(sw_app, assembly_doc)
        
        if not is_subprocess:
            self.set_status("Tamamlandı")
            self.set_progress(1.0)
            self.log("İşlem başarıyla tamamlandı.", "#10b981")
            
    def run_process_immediate_mode(self, codes, vault, is_subprocess=False):
        """YENİ AKIŞ: Bulundu -> Hemen ekle (checkbox işaretli değil)"""
        if is_subprocess: self.log(f"Alt Süreç Başladı: Immediate Mode ({len(codes)} parça)", "#6366f1")

        # Ensure Vault is valid
        try:
            _ = vault.Name
        except:
            if is_subprocess: self.log("Alt süreç için PDM bağlantısı tazecleniyor...", "#3b82f6")
            vault = self.get_pdm_vault()


        # SolidWorks'ü başlat ve montajı hazırla
        self.set_status("SolidWorks başlatılıyor...")

        sw_app = self.get_sw_app()
        if not sw_app:
            self.set_status("Hata")
            self.log("SolidWorks başlatılamadı. İşlem durduruldu.", "#ef4444")
            return

        assembly_doc, locked_title, asm_title, pre_open_docs, z_offset = self.init_assembly_doc(sw_app)
        if not assembly_doc:
            return

        self.set_status("Parçalar ekleniyor...")

        total_files = len(found_files)
        i = 0
        while i < total_files:
            file_path = found_files[i]
            
            if not self.is_running:
                self.log("İşlem durduruldu.", "#f97316")
                return

            if self.is_paused and self.is_running:
                self.log("İşlem duraklatıldı.", "#0ea5e9")
            while self.is_paused and self.is_running:
                time.sleep(0.5)

            # Check if SolidWorks is still running
            sw_alive = True
            try:
                _ = sw_app.Visible
            except Exception:
                sw_alive = False
            
            if not sw_alive:
                self.log("SolidWorks kapandı! Yeniden başlatılıyor ve tüm parçalar tekrar eklenecek...", "#f59e0b")
                sw_app = self.get_sw_app()
                if not sw_app:
                    self.log("SolidWorks başlatılamadı. İşlem durduruldu.", "#ef4444")
                    self.set_status("Hata")
                    return
                assembly_doc, locked_title, asm_title, pre_open_docs, z_offset = self.init_assembly_doc(sw_app)
                if not assembly_doc:
                    self.log("Montaj oluşturulamadı. İşlem durduruldu.", "#ef4444")
                    self.set_status("Hata")
                    return
                # Restart from beginning
                i = 0
                self.log("Tüm parçalar baştan ekleniyor...", "#3b82f6")
                continue

            if locked_title:
                try:
                    sw_app.ActivateDoc3(locked_title, False, 0, None)
                except Exception:
                    pass

            assembly_doc = self.ensure_assembly_doc(sw_app, assembly_doc)
            if not assembly_doc:
                self.log("Montaj bağlantısı koptu! SolidWorks yeniden başlatılıyor ve tüm parçalar tekrar eklenecek...", "#f59e0b")
                sw_app = self.get_sw_app()
                if not sw_app:
                    self.log("SolidWorks başlatılamadı. İşlem durduruldu.", "#ef4444")
                    self.set_status("Hata")
                    return
                assembly_doc, locked_title, asm_title, pre_open_docs, z_offset = self.init_assembly_doc(sw_app)
                if not assembly_doc:
                    self.log("Montaj oluşturulamadı. İşlem durduruldu.", "#ef4444")
                    self.set_status("Hata")
                    return
                # Restart from beginning
                i = 0
                self.log("Tüm parçalar baştan ekleniyor...", "#3b82f6")
                continue

            result = self.add_component_to_assembly(sw_app, assembly_doc, file_path, z_offset, asm_title, pre_open_docs)
            success, z_offset, needs_restart = result[0], result[1], result[2] if len(result) > 2 else False
            
            # If COM connection was lost, restart and add all parts from beginning
            if needs_restart:
                self.log("Bağlantı hatası! SolidWorks yeniden başlatılıyor ve tüm parçalar tekrar eklenecek...", "#f59e0b")
                sw_app = self.get_sw_app()
                if sw_app:
                    assembly_doc, locked_title, asm_title, pre_open_docs, z_offset = self.init_assembly_doc(sw_app)
                    if assembly_doc:
                        # Restart from beginning
                        i = 0
                        self.log("Tüm parçalar baştan ekleniyor...", "#3b82f6")
                        continue
            
            # If failed but not due to COM error, check if SW is still alive
            if not success and not needs_restart:
                sw_alive = True
                try:
                    _ = sw_app.Visible
                except Exception:
                    sw_alive = False
                
                if not sw_alive:
                    self.log("SolidWorks bağlantısı koptu! Yeniden başlatılıyor ve tüm parçalar tekrar eklenecek...", "#f59e0b")
                    sw_app = self.get_sw_app()
                    if sw_app:
                        assembly_doc, locked_title, asm_title, pre_open_docs, z_offset = self.init_assembly_doc(sw_app)
                        if assembly_doc:
                            # Restart from beginning
                            i = 0
                            self.log("Tüm parçalar baştan ekleniyor...", "#3b82f6")
                            continue
            
            self.set_progress(0.5 + (0.5 * (i + 1) / total_files))
            i += 1

        self.set_status("Tamamlandı")
        self.apply_cleanup_logic(sw_app, assembly_doc)
        self.set_progress(1.0)
        self.log("İşlem başarıyla tamamlandı.", "#10b981")

    
    def run_process_immediate_mode(self, codes, vault):
        """YENİ AKIŞ: Bulundu -> Hemen ekle (checkbox işaretli değil)"""
        # SolidWorks'ü başlat ve montajı hazırla
        self.set_status("SolidWorks başlatılıyor...")
        sw_app = self.get_sw_app()
        if not sw_app:
            self.set_status("Hata")
            self.log("SolidWorks başlatılamadı. İşlem durduruldu.", "#ef4444")
            return

        assembly_doc, locked_title, asm_title, pre_open_docs, z_offset = self.init_assembly_doc(sw_app)
        if not assembly_doc:
            return

        self.set_status("Parçalar aranıyor ve ekleniyor...")
        total_codes = len(codes)
        added_count = 0
        error_count = 0
        not_found_codes = []
        found_paths = {}  # Cache found paths to avoid re-searching
        
        # Initial stats
        self.update_stats(total=total_codes, success=0, error=0)

        i = 0
        while i < total_codes:
            code = codes[i]
            
            if not self.is_running:
                self.log("İşlem durduruldu.", "#f97316")
                return

            if self.is_paused and self.is_running:
                self.log("İşlem duraklatıldı.", "#0ea5e9")
            while self.is_paused and self.is_running:
                time.sleep(0.5)
            
            # PDM'de ara (use cache if available)
            if code in found_paths:
                path = found_paths[code]
            else:
                path = self.search_file_in_pdm(vault, code)
                if path:
                    found_paths[code] = path
            
            if not self.is_running:
                self.log("İşlem durduruldu.", "#f97316")
                return
            
            if not path:
                if code not in not_found_codes:
                    not_found_codes.append(code)
                    self.log(f"Bulunamadı: {code}", "#ef4444")
                    error_count += 1
                    self.update_stats(error=error_count)
                self.set_progress(0.1 + (0.9 * (i + 1) / total_codes))
                i += 1
                continue
            
            # Dosya bulundu, yerelde olduğundan emin ol
            if not self.ensure_local_file(vault, path):
                self.log(f"Bulunamadı: {code}", "#ef4444")
                if code not in not_found_codes:
                    not_found_codes.append(code)
                    error_count += 1
                    self.update_stats(error=error_count)
                self.set_progress(0.1 + (0.9 * (i + 1) / total_codes))
                i += 1
                continue
            
            # Bulundu log'u
            self.log(f"Bulundu: {code}", "#10b981")

            # Check if SolidWorks is still running
            sw_alive = True
            try:
                _ = sw_app.Visible
            except Exception:
                sw_alive = False
            
            if not sw_alive:
                self.log("SolidWorks kapandı! Yeniden başlatılıyor ve tüm parçalar tekrar eklenecek...", "#f59e0b")
                sw_app = self.get_sw_app()
                if not sw_app:
                    self.log("SolidWorks başlatılamadı. İşlem durduruldu.", "#ef4444")
                    self.set_status("Hata")
                    return
                assembly_doc, locked_title, asm_title, pre_open_docs, z_offset = self.init_assembly_doc(sw_app)
                if not assembly_doc:
                    self.log("Montaj oluşturulamadı. İşlem durduruldu.", "#ef4444")
                    self.set_status("Hata")
                    return
                # Restart from beginning, reset counters
                i = 0
                added_count = 0
                self.update_stats(total=total_codes, success=0, error=error_count)
                self.log("Tüm parçalar baştan ekleniyor...", "#3b82f6")
                continue

            # HEMEN MONTAJA EKLE
            if locked_title:
                try:
                    sw_app.ActivateDoc3(locked_title, False, 0, None)
                except Exception:
                    pass

            assembly_doc = self.ensure_assembly_doc(sw_app, assembly_doc)
            if not assembly_doc:
                self.log("Montaj bağlantısı koptu! SolidWorks yeniden başlatılıyor ve tüm parçalar tekrar eklenecek...", "#f59e0b")
                sw_app = self.get_sw_app()
                if not sw_app:
                    self.log("SolidWorks başlatılamadı. İşlem durduruldu.", "#ef4444")
                    self.set_status("Hata")
                    return
                assembly_doc, locked_title, asm_title, pre_open_docs, z_offset = self.init_assembly_doc(sw_app)
                if not assembly_doc:
                    self.log("Montaj oluşturulamadı. İşlem durduruldu.", "#ef4444")
                    self.set_status("Hata")
                    return
                # Restart from beginning, reset counters
                i = 0
                added_count = 0
                self.update_stats(total=total_codes, success=0, error=error_count)
                self.log("Tüm parçalar baştan ekleniyor...", "#3b82f6")
                continue

            result = self.add_component_to_assembly(sw_app, assembly_doc, path, z_offset, asm_title, pre_open_docs)
            success, z_offset, needs_restart = result[0], result[1], result[2] if len(result) > 2 else False
            
            # If COM connection was lost, restart and add all parts from beginning
            if needs_restart:
                self.log("Bağlantı hatası! SolidWorks yeniden başlatılıyor ve tüm parçalar tekrar eklenecek...", "#f59e0b")
                sw_app = self.get_sw_app()
                if sw_app:
                    assembly_doc, locked_title, asm_title, pre_open_docs, z_offset = self.init_assembly_doc(sw_app)
                    if assembly_doc:
                        # Restart from beginning, reset counters
                        i = 0
                        added_count = 0
                        self.update_stats(total=total_codes, success=0, error=error_count)
                        self.log("Tüm parçalar baştan ekleniyor...", "#3b82f6")
                        continue
            
            # If failed but not due to COM error, check if SW is still alive
            if not success and not needs_restart:
                sw_alive = True
                try:
                    _ = sw_app.Visible
                except Exception:
                    sw_alive = False
                
                if not sw_alive:
                    self.log("SolidWorks bağlantısı koptu! Yeniden başlatılıyor ve tüm parçalar tekrar eklenecek...", "#f59e0b")
                    sw_app = self.get_sw_app()
                    if sw_app:
                        assembly_doc, locked_title, asm_title, pre_open_docs, z_offset = self.init_assembly_doc(sw_app)
                        if assembly_doc:
                            # Restart from beginning, reset counters
                            i = 0
                            added_count = 0
                            self.update_stats(total=total_codes, success=0, error=error_count)
                            self.log("Tüm parçalar baştan ekleniyor...", "#3b82f6")
                            continue
            
            if success:
                added_count += 1
                self.update_stats(success=added_count)
            else:
                error_count += 1
                self.update_stats(error=error_count)

            self.set_progress(0.1 + (0.9 * (i + 1) / total_codes))
            i += 1

        # Özet bilgi
        # Özet bilgi
        if not_found_codes:
            not_found_str = ",".join(not_found_codes)
            self.log(f"Bulunamayan SAP kodları ({len(not_found_codes)} adet): {not_found_str} PDM'de yok.", "#f59e0b")
        
        self.apply_cleanup_logic(sw_app, assembly_doc)

        if not is_subprocess:
            if added_count > 0:
                self.log(f"Toplam {added_count} parça montaja eklendi.", "#10b981")
                self.set_status("Tamamlandı")
                self.set_progress(1.0)
                self.log("İşlem başarıyla tamamlandı.", "#10b981")
            else:
                self.log("Hiçbir parça eklenemedi.", "#f59e0b")
                self.set_status("Tamamlandı")
                self.set_progress(1.0)
