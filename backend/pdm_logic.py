import json
import os
import sys
import time
import subprocess
import ctypes
import threading
import win32com.client
import pythoncom
import winreg
from queue import Queue

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
    Adds \\\\?\\ prefix when needed and handles UNC paths so Windows APIs can read very long paths.
    """
    if not path:
        return path
    try:
        norm = os.path.abspath(path)
        if norm.startswith("\\\\?\\"):
            return norm
        if norm.startswith("\\\\"):
            return "\\\\?\\UNC\\" + norm[2:]
        if len(norm) >= 240:
            return "\\\\?\\" + norm
        return norm
    except Exception:
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
            self.log("İşlem duraklatıldı.", "#f59e0b")
            self.set_status("Duraklatıldı")

    def resume_process(self):
        if self.is_running and self.is_paused:
            self.is_paused = False
            self.log("İşlem devam ettiriliyor...", "#3b82f6")
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
            if "Geçersiz sınıf dizesi" in err_str or "-2147221005" in err_str:
                self.log("PDM Bağlanılmadı. Lütfen PDM istemcisinin kurulu ve çalışır durumda olduğundan emin olun.", "#ef4444")
            else:
                self.log(f"PDM Bağlantı Hatası: {err_str}", "#ef4444")
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
        # Try searching by PDM variables first
        for var_name in PDM_VAR_NAMES:
            try:
                search = vault.CreateSearch()
                search.AddVariable(var_name, sap_code)
                result = search.GetFirstResult()
                found_files = []
                while result:
                    found_files.append(result.Name)
                    ext = os.path.splitext(result.Name)[1].lower()
                    if ext in PREFERRED_EXTS:
                        self.log(f"  → PDM'de bulundu (değişken: {var_name}): {result.Name}", "#6b7280")
                        return self.map_vault_path(vault, result.Path)
                    result = search.GetNextResult()
                # Log if found files but wrong extension
                if found_files:
                    self.log(f"  → Dosya bulundu ancak desteklenmeyen uzantı: {', '.join(found_files)}", "#6b7280")
            except Exception as e:
                continue
        
        # Try filename search as fallback
        try:
            search = vault.CreateSearch()
            search.FileName = f"*{sap_code}*"
            result = search.GetFirstResult()
            found_files = []
            while result:
                found_files.append(result.Name)
                ext = os.path.splitext(result.Name)[1].lower()
                if ext in PREFERRED_EXTS:
                    self.log(f"  → PDM'de bulundu (dosya adı araması): {result.Name}", "#6b7280")
                    return self.map_vault_path(vault, result.Path)
                result = search.GetNextResult()
            # Log if found files but wrong extension
            if found_files:
                self.log(f"  → Dosya adıyla bulundu ancak desteklenmeyen uzantı: {', '.join(found_files)}", "#6b7280")
        except Exception as e:
            self.log(f"  → Dosya adı ile aranırken bir hata oluştu: {str(e)}", "#6b7280")
        
        return None

    def fetch_latest_revision(self, vault, file_path):
        """
        fetch_pdm_latest.py mantığını kullanarak dosyanın son revizyonunu çeker.
        Dosya yerelde yoksa veya eski sürümse günceller.
        """
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
                self.log(f"  ✗ PDM'de dosya bulunamadı: {file_name}", "#ef4444")
                return False
            
            # Folder object yoksa parent folder'ı al
            if not folder_obj:
                try:
                    folder_obj = file_obj.GetParentFolder()
                except Exception:
                    pass
            
            if not folder_obj:
                self.log(f"  ✗ Dosya klasör bilgisi alınamadı: {file_name}", "#ef4444")
                return False
            
            # Yerel ve sunucu sürümlerini karşılaştır
            try:
                local_version = file_obj.GetLocalVersionNo(folder_obj.ID)
                latest_version = file_obj.CurrentVersion
                
                if os.path.exists(file_path) and local_version >= latest_version:
                    self.log(f"  ✓ Dosya güncel (v{local_version}): {file_name}", "#6b7280")
                    return True
                
                self.log(f"  → Sürüm güncelleniyor (v{local_version} → v{latest_version}): {file_name}", "#3b82f6")
            except Exception as ver_err:
                self.log(f"  → Sürüm bilgisi alınamadı, son sürüm çekiliyor: {file_name}", "#f59e0b")
            
            # GetFileCopy ile son revizyonu çek (fetch_pdm_latest.py mantığı)
            try:
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
                    self.log(f"  ✗ Dosya kopyalama hatası: {alt_err}", "#ef4444")
                    return False
            
            # Dosyanın indirilmesini bekle
            for attempt in range(30):  # 7.5 saniye maksimum
                if os.path.exists(file_path):
                    # Dosya boyutunu kontrol et (indirme tamamlandı mı?)
                    try:
                        size = os.path.getsize(file_path)
                        if size > 0:
                            self.log(f"  ✓ Son sürüm indirildi: {file_name}", "#10b981")
                            return True
                    except Exception:
                        pass
                time.sleep(0.25)
            
            # Son kontrol
            if os.path.exists(file_path):
                self.log(f"  ✓ Dosya indirildi: {file_name}", "#10b981")
                return True
            
            self.log(f"  ✗ Dosya indirme zaman aşımına uğradı: {file_name}", "#ef4444")
            return False
            
        except Exception as e:
            self.log(f"  ✗ Son sürüm çekilirken hata oluştu: {e}", "#ef4444")
            return False

    def ensure_local_file(self, vault, file_path):
        """
        Dosyanın yerelde olduğundan ve güncel olduğundan emin ol.
        Yoksa veya eskiyse PDM'den son sürümü çek.
        """
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
                        self.log(f"  ✓ Dosya güncel (v{local_version}): {file_name}", "#6b7280")
                        return True
                    else:
                        self.log(f"  → Güncelleme gerekli (v{local_version} → v{latest_version}): {file_name}", "#f59e0b")
            except Exception as ver_check_err:
                # Sürüm kontrolü başarısız, yine de güncellemeyi dene
                self.log(f"  → Sürüm kontrolü yapılamadı, güncelleniyor: {file_name}", "#f59e0b")
        else:
            self.log(f"  → Dosya yerelde yok, indiriliyor: {file_name}", "#f59e0b")
        
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
            self.log(f"✓ Eklendi: {os.path.basename(file_path)} (Z={z_offset:.3f}m)", "#10b981")
            new_z_offset = z_offset - 0.3  # offset_step
            success = True
        else:
            self.log(f"Eklenemedi: {os.path.basename(file_path)} -> {' | '.join(errors) if errors else 'bilinmeyen'}", "#f59e0b")

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

        return success, new_z_offset

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
            self.log(f"  ✗ Bileşen açılırken hata oluştu: {str(e)}", "#6b7280")
            return None, False


    def run_process(self, codes):
        pythoncom.CoInitialize()
        self.is_running = True
        try:
            self.set_progress(0.1)
            self.set_status("PDM'e bağlanılıyor...")
            vault = self.get_pdm_vault()
            if not vault:
                self.set_status("Hata")
                self.log("PDM bağlantısı sağlanamadı. İşlem durduruldu.", "#ef4444")
                return

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
            
            # Eğer işlem bittiğinde statü hala aktif bir durumdaysa, Durduruldu olarak işaretle
            final_statuses = ["Tamamlandı", "Hata", "İptal", "Durduruldu"]
            if self.current_status not in final_statuses:
                self.set_status("Durduruldu")

            vault = None
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
    
    def run_process_batch_mode(self, codes, vault):
        """ESKİ AKIŞ: Önce tüm parçaları ara, sonra montaja ekle (checkbox işaretli)"""
        found_files = []
        not_found_codes = []

        self.set_status("Parçalar aranıyor...")
        total_codes = len(codes)
        
        # Initialize stats
        self.update_stats(total=total_codes, success=0, error=0)
        
        for i, code in enumerate(codes):
            if not self.is_running:
                return
            
            while self.is_paused and self.is_running:
                time.sleep(0.5)
            path = self.search_file_in_pdm(vault, code)
            if path:
                if self.ensure_local_file(vault, path):
                    found_files.append(path)
                    self.log(f"Bulundu: {code}", "#10b981")
                    self.update_stats(success=len(found_files))
                else:
                    not_found_codes.append(code)
                    self.log(f"Bulunamadı: {code}", "#ef4444")
                    self.update_stats(error=len(not_found_codes))
            else:
                not_found_codes.append(code)
                self.log(f"Bulunamadı: {code}", "#ef4444")
                self.update_stats(error=len(not_found_codes))
            self.set_progress(0.1 + (0.4 * (i + 1) / total_codes))

        if not_found_codes:
            not_found_str = ",".join(not_found_codes)
            self.log(f"Bulunamayan SAP kodları ({len(not_found_codes)} adet): {not_found_str} PDM'de yok.", "#f59e0b")
            self.log("Bulunamayan parçalar var, montaj iptal edildi.", "#f59e0b")
            self.set_progress(1)
            self.set_status("İptal")
            return

        if not found_files:
            self.log("Eklenecek parça bulunamadı.", "#f59e0b")
            self.set_progress(0)
            self.set_status("İptal")
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
        for i, file_path in enumerate(found_files):
            if not self.is_running:
                return

            while self.is_paused and self.is_running:
                time.sleep(0.5)

            if locked_title:
                try:
                    sw_app.ActivateDoc3(locked_title, False, 0, None)
                except Exception:
                    pass

            assembly_doc = self.ensure_assembly_doc(sw_app, assembly_doc)
            if not assembly_doc:
                self.log("Montaj oturumu kaybedildi.", "#ef4444")
                return

            success, z_offset = self.add_component_to_assembly(sw_app, assembly_doc, file_path, z_offset, asm_title, pre_open_docs)
            self.set_progress(0.5 + (0.5 * (i + 1) / total_files))

        self.set_status("Tamamlandı")
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
        
        # Initial stats
        self.update_stats(total=total_codes, success=0, error=0)

        for i, code in enumerate(codes):
            if not self.is_running:
                return

            while self.is_paused and self.is_running:
                time.sleep(0.5)
            
            # PDM'de ara
            path = self.search_file_in_pdm(vault, code)
            
            if not path:
                not_found_codes.append(code)
                self.log(f"Bulunamadı: {code}", "#ef4444")
                error_count += 1
                self.update_stats(error=error_count)
                self.set_progress(0.1 + (0.9 * (i + 1) / total_codes))
                continue
            
            # Dosya bulundu, yerelde olduğundan emin ol
            if not self.ensure_local_file(vault, path):
                self.log(f"Bulunamadı: {code}", "#ef4444")
                not_found_codes.append(code)
                error_count += 1
                self.update_stats(error=error_count)
                self.set_progress(0.1 + (0.9 * (i + 1) / total_codes))
                continue
            
            # Bulundu log'u
            self.log(f"Bulundu: {code}", "#10b981")

            # HEMEN MONTAJA EKLE
            if locked_title:
                try:
                    sw_app.ActivateDoc3(locked_title, False, 0, None)
                except Exception:
                    pass

            assembly_doc = self.ensure_assembly_doc(sw_app, assembly_doc)
            if not assembly_doc:
                self.log("Montaj oturumu kaybedildi.", "#ef4444")
                return

            success, z_offset = self.add_component_to_assembly(sw_app, assembly_doc, path, z_offset, asm_title, pre_open_docs)
            if success:
                added_count += 1
                self.update_stats(success=added_count)
            else:
                error_count += 1
                self.update_stats(error=error_count)

            self.set_progress(0.1 + (0.9 * (i + 1) / total_codes))

        # Özet bilgi
        if not_found_codes:
            not_found_str = ",".join(not_found_codes)
            self.log(f"Bulunamayan SAP kodları ({len(not_found_codes)} adet): {not_found_str} PDM'de yok.", "#f59e0b")
        
        if added_count > 0:
            self.log(f"Toplam {added_count} parça montaja eklendi.", "#10b981")
            self.set_status("Tamamlandı")
            self.set_progress(1.0)
            self.log("İşlem başarıyla tamamlandı.", "#10b981")
        else:
            self.log("Hiçbir parça eklenemedi.", "#f59e0b")
            self.set_status("Tamamlandı")
            self.set_progress(1.0)
