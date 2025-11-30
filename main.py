import json
import os
import sys
import time
import subprocess
import ctypes
import threading
import flet as ft
import win32com.client
import pythoncom
import winreg

# --- BU FONKSİYONU İMPORTLARIN ALTINA EKLEYİN ---
def resource_path(relative_path):
    """ PyInstaller ile oluşturulan exe içindeki dosya yolunu bulur """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
# ------------------------------------------------

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

# Neumorphic renk paleti
LIGHT_BG = "#e0e5ec"
LIGHT_TEXT = "#4a4a4a"
LIGHT_SHADOW_DARK = "#a3b1c6"
LIGHT_SHADOW_LIGHT = "#ffffff"
LIGHT_ACCENT = "#ff9f43"

DARK_BG = "#2d3436"
DARK_TEXT = "#dfe6e9"
DARK_SHADOW_DARK = "#1e2324"
DARK_SHADOW_LIGHT = "#3d4649"
DARK_ACCENT = "#74b9ff"

CARD_BG_LIGHT = "#FFFFFF"
CARD_BG_DARK = "#1F2937"

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
    def __init__(self, log_callback, status_callback, progress_callback, add_to_existing_callback, stop_on_not_found_callback):
        self.log = log_callback
        self.set_status = status_callback
        self.set_progress = progress_callback
        self.get_add_to_existing = add_to_existing_callback
        self.get_stop_on_not_found = stop_on_not_found_callback
        self.config = {}
        self.vault_path = read_vault_path_registry()
        self.is_running = False

    def set_vault_path(self, path):
        """Update selected vault path (runtime only)."""
        self.vault_path = path or ""
        write_vault_path_registry(self.vault_path)

    def stop_process(self):
        self.is_running = False

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
            self.log(f"PDM Bağlantı Hatası: {e}", "#ef4444")
            return None

    def get_sw_app(self):
        try:
            sw_app = win32com.client.GetActiveObject("SldWorks.Application")
            self.log("Mevcut SolidWorks oturumu bulundu.", "#2cc985")
            return sw_app
        except Exception:
            self.log("Açık SolidWorks oturumu bulunamadı, başlatılıyor...", "#f59e0b")
        
        try:
            sw_app = win32com.client.Dispatch("SldWorks.Application")
            sw_app.Visible = True
            return sw_app
        except Exception as e:
            self.log(f"SolidWorks başlatılamadı: {e}", "#ef4444")
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
                    self.log(f"  → Dosya bulundu ama yanlış uzantı: {', '.join(found_files)}", "#6b7280")
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
                self.log(f"  → Dosya adıyla bulundu ama yanlış uzantı: {', '.join(found_files)}", "#6b7280")
        except Exception as e:
            self.log(f"  → Dosya adı araması hatası: {str(e)}", "#6b7280")
        
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
                self.log(f"  ✗ Klasör nesnesi alınamadı: {file_name}", "#ef4444")
                return False
            
            # Yerel ve sunucu sürümlerini karşılaştır
            try:
                local_version = file_obj.GetLocalVersionNo(folder_obj.ID)
                latest_version = file_obj.CurrentVersion
                
                if os.path.exists(file_path) and local_version >= latest_version:
                    self.log(f"  ✓ Dosya güncel (v{local_version}): {file_name}", "#6b7280")
                    return True
                
                self.log(f"  → Sürüm güncelleniyor (v{local_version} → v{latest_version}): {file_name}", "#3B82F6")
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
                    self.log(f"  ✗ GetFileCopy hatası: {alt_err}", "#ef4444")
                    return False
            
            # Dosyanın indirilmesini bekle
            for attempt in range(30):  # 7.5 saniye maksimum
                if os.path.exists(file_path):
                    # Dosya boyutunu kontrol et (indirme tamamlandı mı?)
                    try:
                        size = os.path.getsize(file_path)
                        if size > 0:
                            self.log(f"  ✓ Son sürüm indirildi: {file_name}", "#2cc985")
                            return True
                    except Exception:
                        pass
                time.sleep(0.25)
            
            # Son kontrol
            if os.path.exists(file_path):
                self.log(f"  ✓ Dosya indirildi: {file_name}", "#2cc985")
                return True
            
            self.log(f"  ✗ Dosya indirilemedi (timeout): {file_name}", "#ef4444")
            return False
            
        except Exception as e:
            self.log(f"  ✗ fetch_latest_revision hatası: {e}", "#ef4444")
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
                        self.log(f"  ⚠ Dosya açıldı ama local'de yok: {os.path.basename(file_path)}", "#f59e0b")
                    else:
                        self.log(f"  ✔ Dosya başarıyla local'e çekildi: {os.path.basename(file_path)}", "#6b7280")
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
            self.log(f"  ✗ open_component_doc hatası: {str(e)}", "#6b7280")
            return None, False


    def run_process(self, codes):
        pythoncom.CoInitialize()
        self.is_running = True
        try:
            self.set_progress(0.1)
            self.set_status("PDM'e bağlanılıyor...")
            vault = self.get_pdm_vault()
            if not vault:
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
            self.log(f"Kritik Hata: {e}", "#ef4444")
            self.set_status("Hata")
        finally:
            pythoncom.CoUninitialize()
    
    def run_process_batch_mode(self, codes, vault):
        """ESKİ AKIŞ: Önce tüm parçaları ara, sonra montaja ekle (checkbox işaretli)"""
        found_files = []
        not_found_codes = []

        self.set_status("Parçalar aranıyor...")
        total_codes = len(codes)
        for i, code in enumerate(codes):
            if not self.is_running:
                return
            path = self.search_file_in_pdm(vault, code)
            if path:
                if self.ensure_local_file(vault, path):
                    found_files.append(path)
                    self.log(f"Bulundu: {code}", "#2cc985")
                else:
                    not_found_codes.append(code)
                    self.log(f"Yerelde bulunamadı: {code}", "#ef4444")
            else:
                not_found_codes.append(code)
                self.log(f"Bulunamadı: {code}", "#ef4444")
            self.set_progress(0.1 + (0.4 * (i + 1) / total_codes))

        if not_found_codes:
            not_found_str = ",".join(not_found_codes)
            self.log(f"Bulunamayan SAP kodları: {not_found_str} PDM'de yok", "#f59e0b")
            self.log("Bulunamayan parçalar var, montaj iptal edildi.", "#f59e0b")
            self.set_progress(0)
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
            return

        add_to_existing = self.get_add_to_existing()
        locked_title = None  # Kilitlenecek montaj başlığı
        assembly_doc = None
        if add_to_existing:
            assembly_doc = self.get_active_assembly(sw_app)
            if assembly_doc:
                self.log("Mevcut montaja parçalar eklenecek.", "#2cc985")
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
                return
            assembly_doc = new_doc
            # YENİ MONTAJ OLUŞTURULDU - BAŞLIĞI KİLİTLE
            try:
                locked_title = assembly_doc.GetTitle() or ""
                self.log(f"Yeni montaj kilitlendi: {locked_title}", "#3B82F6")
            except Exception:
                locked_title = ""

        assembly_doc = self.ensure_assembly_doc(sw_app, assembly_doc)
        if not assembly_doc or self.doc_type_safe(assembly_doc) != SW_DOC_ASSEMBLY:
            self.log("Aktif montaj alınamadı.", "#ef4444")
            return

        self.set_status("Parçalar ekleniyor...")
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

        offset_step = -0.3
        is_adding_to_existing = self.get_add_to_existing()
        
        if is_adding_to_existing:
            existing_count = 0
            try:
                comps_before = assembly_doc.GetComponents(True) or []
                existing_count = len(comps_before)
            except Exception:
                pass
            z_offset = existing_count * offset_step
            if existing_count == 0:
                self.log(f"Montaj boş, yeni parçalar Z=0m'den başlayacak", "#3B82F6")
            else:
                self.log(f"Montajda {existing_count} parça var, yeni parçalar Z={z_offset:.3f}m'den başlayacak", "#3B82F6")
        else:
            z_offset = 0.0

        total_files = len(found_files)
        for i, file_path in enumerate(found_files):
            if not self.is_running:
                return
            
            if locked_title:
                try:
                    sw_app.ActivateDoc3(locked_title, False, 0, None)
                except Exception:
                    pass
            
            assembly_doc = self.ensure_assembly_doc(sw_app, assembly_doc)
            if not assembly_doc:
                self.log("Montaj oturumu kaybedildi.", "#ef4444")
                return
            if not os.path.exists(file_path):
                if not self.ensure_local_file(vault, file_path) or not os.path.exists(file_path):
                    self.log(f"Local copy missing: {file_path}", "#ef4444")
                    continue

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

            if comp:
                self.log(f"✓ Eklendi: {os.path.basename(file_path)} (Z={z_offset:.3f}m)", "#2cc985")
                z_offset += offset_step
            else:
                self.log(f"Eklenemedi: {os.path.basename(file_path)} -> {' | '.join(errors) if errors else 'bilinmeyen'}", "#f59e0b")

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

            self.set_progress(0.5 + (0.5 * (i + 1) / total_files))

        self.set_status("Tamamlandı")
        self.set_progress(1.0)
        self.log("İşlem başarıyla tamamlandı.", "#2cc985")
    
    def run_process_immediate_mode(self, codes, vault):
        """YENİ AKIŞ: Bulundu -> Hemen ekle (checkbox işaretli değil)"""
        # SolidWorks'ü başlat ve montajı hazırla
        self.set_status("SolidWorks başlatılıyor...")
        sw_app = self.get_sw_app()
        if not sw_app:
            return

        add_to_existing = self.get_add_to_existing()
        locked_title = None  # Kilitlenecek montaj başlığı
        assembly_doc = None
        if add_to_existing:
            assembly_doc = self.get_active_assembly(sw_app)
            if assembly_doc:
                self.log("Mevcut montaja parçalar eklenecek.", "#2cc985")
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
                return
            assembly_doc = new_doc
            # YENİ MONTAJ OLUŞTURULDU - BAŞLIĞI KİLİTLE
            try:
                locked_title = assembly_doc.GetTitle() or ""
                self.log(f"Yeni montaj kilitlendi: {locked_title}", "#3B82F6")
            except Exception:
                locked_title = ""

        assembly_doc = self.ensure_assembly_doc(sw_app, assembly_doc)
        if not assembly_doc or self.doc_type_safe(assembly_doc) != SW_DOC_ASSEMBLY:
            self.log("Aktif montaj alınamadı.", "#ef4444")
            return

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

        offset_step = -0.3
        is_adding_to_existing = self.get_add_to_existing()
        
        if is_adding_to_existing:
            existing_count = 0
            try:
                comps_before = assembly_doc.GetComponents(True) or []
                existing_count = len(comps_before)
            except Exception:
                pass
            z_offset = existing_count * offset_step
            if existing_count == 0:
                self.log(f"Montaj boş, yeni parçalar Z=0m'den başlayacak", "#3B82F6")
            else:
                self.log(f"Montajda {existing_count} parça var, yeni parçalar Z={z_offset:.3f}m'den başlayacak", "#3B82F6")
        else:
            z_offset = 0.0

        self.set_status("Parçalar aranıyor ve ekleniyor...")
        total_codes = len(codes)
        added_count = 0
        not_found_codes = []

        for i, code in enumerate(codes):
            if not self.is_running:
                return
            
            # PDM'de ara
            path = self.search_file_in_pdm(vault, code)
            
            if not path:
                not_found_codes.append(code)
                self.log(f"Bulunamadı: {code}", "#ef4444")
                self.set_progress(0.1 + (0.9 * (i + 1) / total_codes))
                continue
            
            # Dosya bulundu, yerelde olduğundan emin ol
            if not self.ensure_local_file(vault, path):
                self.log(f"Yerelde bulunamadı: {code}", "#ef4444")
                not_found_codes.append(code)
                self.set_progress(0.1 + (0.9 * (i + 1) / total_codes))
                continue
            
            # Bulundu log'u
            self.log(f"Bulundu: {code}", "#2cc985")
            
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
            
            if not os.path.exists(path):
                self.log(f"Local copy missing: {path}", "#ef4444")
                self.set_progress(0.1 + (0.9 * (i + 1) / total_codes))
                continue

            path_candidates, target_paths = self.build_path_candidates(path)

            comp = None
            errors = []
            comp_doc = None
            
            try:
                existing_names = {getattr(c, "Name2", "") for c in (assembly_doc.GetComponents(True) or []) if c}
            except Exception:
                existing_names = set()

            ext = os.path.splitext(path)[1].lower()
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

            if comp:
                self.log(f"✓ Eklendi: {os.path.basename(path)} (Z={z_offset:.3f}m)", "#2cc985")
                added_count += 1
                z_offset += offset_step
            else:
                self.log(f"Eklenemedi: {os.path.basename(path)} -> {' | '.join(errors) if errors else 'bilinmeyen'}", "#f59e0b")

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
                base_title = os.path.basename(path)
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

            self.set_progress(0.1 + (0.9 * (i + 1) / total_codes))

        # Özet bilgi
        if not_found_codes:
            not_found_str = ",".join(not_found_codes)
            self.log(f"Bulunamayan SAP kodları ({len(not_found_codes)} adet): {not_found_str}", "#f59e0b")
        
        if added_count > 0:
            self.log(f"Toplam {added_count} parça montaja eklendi.", "#2cc985")
            self.set_status("Tamamlandı")
            self.set_progress(1.0)
            self.log("İşlem başarıyla tamamlandı.", "#2cc985")
        else:
            self.log("Hiçbir parça eklenemedi.", "#f59e0b")
            self.set_status("Tamamlandı")
            self.set_progress(1.0)


# --- Custom UI Components ---

def hex_opacity(hex_color, opacity):
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 6:
        alpha = int(opacity * 255)
        return f"#{alpha:02x}{hex_color}"
    return f"#{hex_color}"

class ModernProgressBar(ft.Container):
    def __init__(self, width=None, height=12, color=LIGHT_ACCENT, bgcolor="#E5E7EB"):
        self.bar = ft.Container(
            width=0,
            height=height,
            border_radius=height,
            bgcolor=color,
            animate=ft.Animation(300, "easeOut"),
        )
        self._stored_width = width
        self._current_value = 0
        super().__init__(
            width=width,
            height=height,
            bgcolor=bgcolor,
            border_radius=height,
            content=self.bar,
            alignment=ft.alignment.center_left,
            visible=True,
            animate=ft.Animation(300, "easeOut")
        )
        
    def set_value(self, value):
        self._current_value = value
        # Use actual container width if available, otherwise use stored width or default
        actual_width = self.width if self.width else (self._stored_width if self._stored_width else 400)
        target_width = actual_width * value
        self.bar.width = target_width
        self.update()
        self.bar.update()

    def set_color(self, color):
        self.bar.bgcolor = color
        self.bar.update()

# --- Modern Flat Arayüz ---

class ModernCard(ft.Container):
    def __init__(self, content, width=None, height=None, expand=False, padding=20):
        super().__init__(
            content=content,
            width=width,
            height=height,
            expand=expand,
            padding=padding,
            border_radius=20,
            bgcolor=CARD_BG_LIGHT,
            shadow=ft.BoxShadow(
                blur_radius=20,
                color="#0D000000",
                offset=ft.Offset(0, 10)
            ),
            animate=ft.Animation(300, "easeOut"),
        )
    
    def update_theme(self, is_dark):
        if is_dark:
            self.bgcolor = CARD_BG_DARK
            self.shadow.color = "#33000000"
        else:
            self.bgcolor = CARD_BG_LIGHT
            self.shadow.color = "#0D000000"
        self.update()

class ModernButton(ft.ElevatedButton):
    def __init__(self, text, icon, on_click, base_color, expand=False, border_radius=None):
        if border_radius is None:
            border_radius = 12
        super().__init__(
            text=text,
            icon=icon,
            on_click=on_click,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=border_radius) if isinstance(border_radius, (int, float)) else ft.RoundedRectangleBorder(radius=border_radius),
                padding=15,
                bgcolor={
                    "": base_color,
                    "hovered": base_color, 
                },
                color="white",
                elevation={"":"4", "hovered":"12"},
                animation_duration=300,
                overlay_color="#1AFFFFFF"
            ),
            expand=expand,
            width=10000, # Ensure full width when not expanded in a Row
            height=50,   # Increased height
            animate_scale=ft.Animation(200, ft.AnimationCurve.EASE_OUT_CUBIC),
            scale=1,
            on_hover=self.handle_hover
        )

    def handle_hover(self, e):
        self.scale = 1.05 if e.data == "true" else 1.0
        self.update()



def main(page: ft.Page):
    page.title = "PDM Montaj Sihirbazı"
    page.window_icon = resource_path("logo.png")
    page.theme_mode = ft.ThemeMode.LIGHT # Default to Light for this design
    page.padding = 20
    page.window_width = 1200
    page.window_height = 800
    page.bgcolor = LIGHT_BG
    
    def set_min_size(e):
        page.window_min_width = 1000
        page.window_min_height = 600
        page.update()
        
    page.on_resize = set_min_size
    page.update()
    
    if os.path.exists(resource_path("logo.png")):
        page.window_icon = resource_path("logo.png")

    # --- State & Logic ---
    log_lines = ft.ListView(expand=True, spacing=5, padding=10, auto_scroll=True)
    
    # Track not found codes for copying
    not_found_codes_list = []
    
    # Dashboard Stats
    processed_count = ft.Text("0", size=24, weight="bold")
    success_count = ft.Text("0", size=24, weight="bold", color="green")
    error_count = ft.Text("0", size=24, weight="bold", color="red")
    
    # Copy button for not found codes
    copy_button_icon = ft.Icon("content_copy", color="white", size=16)
    copy_button_text = ft.Text("BULUNAMAYANLARI KOPYALA", size=12, weight="bold", color="white")
    
    def copy_not_found(e):
        if not_found_codes_list:
            codes_text = ",".join(not_found_codes_list) + " PDM'de yok"
            page.set_clipboard(codes_text)
            # Show feedback
            copy_button_icon.name = "check"
            copy_button_text.value = "KOPYALANDI"
            copy_button.bgcolor = "#22C55E"
            copy_button.update()
            # Reset after 2 seconds
            import time
            def reset_button():
                time.sleep(2)
                copy_button_icon.name = "content_copy"
                copy_button_text.value = "BULUNAMAYANLARI KOPYALA"
                copy_button.bgcolor = "#EF4444"
                copy_button.update()
            threading.Thread(target=reset_button, daemon=True).start()
    
    copy_button = ft.Container(
        content=ft.Row([
            copy_button_icon,
            copy_button_text,
        ], spacing=8, alignment="center"),
        bgcolor="#EF4444",
        padding=ft.padding.symmetric(horizontal=20, vertical=12),
        border_radius=12,
        on_click=copy_not_found,
        visible=False,  # Hidden by default
        animate=ft.Animation(300, "easeOut"),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=8,
            color="#40EF4444",
            offset=ft.Offset(0, 2),
        ),
    )
    
    # Big Status Display
    big_status_text = ft.Text("HAZIR", size=30, weight="bold", color=LIGHT_ACCENT)
    
    def add_log(message, color=None):
        import datetime
        # Skip noisy info messages
        skip_patterns = [
            "PDM'de dosya nesnesi",
            "PDM'de bulundu",
            "OK Dosya zaten local'de",
        ]
        if any(pat in message for pat in skip_patterns):
            return
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        max_len = 180
        display_message = message if len(message) <= max_len else message[:max_len] + " ..."

        icon_name = "info_outline"
        if color == "#2cc985": # Green color
            icon_name = "check_circle"
            # Only count "Bulundu:" messages as success
            if "Bulundu:" in message and not "oturumu" in message:
                success_count.value = str(int(success_count.value) + 1)
        elif color == "#ef4444": # Error (Not Found)
            icon_name = "error"
            error_count.value = str(int(error_count.value) + 1)
            # Extract code from message "Bulunamadı: CODE"
            if "Bulunamadı:" in message:
                code = message.replace("Bulunamadı:", "").strip()
                if code not in not_found_codes_list:
                    not_found_codes_list.append(code)
                # Show copy button if there are errors
                copy_button.visible = True
                copy_button.update()
        
        success_count.update()
        error_count.update()
        
        base_color = "grey"
        text_color = base_color if color in (None, "#6b7280") else color
        
        log_entry = ft.Container(
            content=ft.Row([
                ft.Text(timestamp, size=11, color=base_color, font_family="Consolas"),
                ft.Icon(icon_name, size=16, color=text_color),
                ft.Text(display_message, size=13, color=text_color, font_family="Consolas", selectable=True, expand=True),
            ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.symmetric(vertical=2),
            border=ft.border.only(bottom=ft.BorderSide(1, "#1A808080")),
            tooltip=message if display_message != message else None
        )
        
        log_lines.controls.append(log_entry)
        log_lines.update()

    status_text = ft.Text("Hazır", weight=ft.FontWeight.BOLD)
    
    # Modern Gradient Progress Bar with smooth animations
    # Using flex-based layout for guaranteed percentage-based progress
    
    # Filled portion (will grow from 0 to 100%) with beautiful gradient
    progress_filled = ft.Container(
        expand=0,  # Start with 0
        height=12,
        border_radius=ft.border_radius.only(top_left=12, bottom_left=12),
        gradient=ft.LinearGradient(
            begin=ft.alignment.center_left,
            end=ft.alignment.center_right,
            colors=["#FF6B6B", "#4ECDC4", "#45B7D1"],
        ),
        shadow=ft.BoxShadow(
            spread_radius=1,
            blur_radius=8,
            color="#40FF6B6B",
            offset=ft.Offset(0, 0),
        ),
        animate=ft.Animation(600, ft.AnimationCurve.EASE_IN_OUT),
    )
    
    # Empty portion (will shrink from 100 to 0%)
    progress_empty = ft.Container(
        expand=100,  # Start with 100
        height=12,
        border_radius=ft.border_radius.only(top_right=12, bottom_right=12),
        bgcolor="#E5E7EB",
        animate=ft.Animation(600, ft.AnimationCurve.EASE_IN_OUT),
    )
    
    # Row containing both portions - NO BORDER
    progress_bar_container = ft.Container(
        content=ft.Row(
            [
                progress_filled,
                progress_empty,
            ],
            spacing=0,
            expand=True,
        ),
        height=12,
        border_radius=12,
        bgcolor="#E5E7EB",
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=4,
            color="#20000000",
            offset=ft.Offset(0, 2),
        ),
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
    )
    
    # Store reference to progress widget
    progress_bar_widget = progress_filled
    
    def update_status(text):
        status_text.value = text
        status_text.update()

    def update_progress(val):
        # Convert 0.0-1.0 to 0-100 for expand values
        filled_expand = int(val * 100)
        empty_expand = 100 - filled_expand
        
        # Update expand values for smooth animation
        progress_filled.expand = max(0, filled_expand)
        progress_empty.expand = max(1, empty_expand)  # Keep at least 1 to maintain visibility
        
        # If at 100%, hide empty portion completely
        if val >= 1.0:
            progress_filled.expand = 100
            progress_empty.expand = 0
            progress_filled.border_radius = 12  # Full border radius when complete
        elif val <= 0:
            progress_filled.expand = 0
            progress_empty.expand = 100
            progress_filled.border_radius = ft.border_radius.only(top_left=12, bottom_left=12)
        else:
            progress_filled.border_radius = ft.border_radius.only(top_left=12, bottom_left=12)
        
        progress_filled.update()
        progress_empty.update()

    # Checkbox for adding to existing assembly
    add_to_existing_checkbox = ft.Checkbox(value=False)
    
    # Checkbox for stopping if parts not found
    stop_on_not_found_checkbox = ft.Checkbox(value=True)
    
    # Checkbox for processing duplicate SAP codes only once
    dedupe_codes_checkbox = ft.Checkbox(value=True)
    
    def get_add_to_existing():
        return add_to_existing_checkbox.value
    
    def get_stop_on_not_found():
        return stop_on_not_found_checkbox.value

    logic = LogicHandler(add_log, update_status, update_progress, get_add_to_existing, get_stop_on_not_found)

    vault_path_text = ft.Text(
        logic.vault_path or "Seçilmedi",
        size=12,
        expand=True,
        no_wrap=True,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

    def handle_vault_pick(e):
        if not e.path:
            return
        selected_path = os.path.normpath(e.path)
        logic.set_vault_path(selected_path)
        vault_path_text.value = selected_path
        vault_path_text.update()
        add_log(f"Kasa yolu güncellendi: {selected_path}", "#3B82F6")

    # --- Dashboard Components ---
    class DashboardCard(ft.Container):
        def __init__(self, title, value_control, icon_name, icon_color):
            self.title_text = ft.Text(title, size=12, color="grey", weight="bold")
            super().__init__(
                content=ft.Row([
                    ft.Container(
                        content=ft.Icon(icon_name, size=24, color=icon_color),
                        padding=10,
                        bgcolor=hex_opacity(icon_color, 0.1),
                        border_radius=10
                    ),
                    ft.Column([
                        self.title_text,
                        value_control
                    ], spacing=2)
                ], alignment="center"),
                padding=15,
                border_radius=15,
                bgcolor="#80FFFFFF", # Slight transparency
                expand=True,
                border=ft.border.all(1, "#1A808080")
            )
        
        def update_theme(self, is_dark):
            self.title_text.color = "white" if is_dark else "grey"
            self.title_text.update()

    # --- UI Elements ---
    
    theme_icon = ft.Icon("nightlight_round", size=20)
    
    def toggle_theme(e):
        is_dark = page.theme_mode == ft.ThemeMode.LIGHT
        page.theme_mode = ft.ThemeMode.DARK if is_dark else ft.ThemeMode.LIGHT
        
        bg = DARK_BG if is_dark else LIGHT_BG
        accent = DARK_ACCENT if is_dark else LIGHT_ACCENT
        
        page.bgcolor = bg
        theme_icon.name = "nightlight_round" if is_dark else "wb_sunny"
        theme_icon.color = accent
        
        for control in [sidebar_card, header_card, input_card, log_card]:
            control.update_theme(is_dark)
            
        for card in [card_total, card_success, card_error]:
            card.update_theme(is_dark)
            
        status_text.color = accent
        
        # Update gradient colors based on theme
        if is_dark:
            progress_filled.gradient = ft.LinearGradient(
                begin=ft.alignment.center_left,
                end=ft.alignment.center_right,
                colors=["#667EEA", "#764BA2", "#F093FB"],
            )
            progress_empty.bgcolor = "#374151"
            progress_bar_container.bgcolor = "#374151"
            progress_filled.shadow = ft.BoxShadow(
                spread_radius=1,
                blur_radius=10,
                color="#60667EEA",
                offset=ft.Offset(0, 0),
            )
        else:
            progress_filled.gradient = ft.LinearGradient(
                begin=ft.alignment.center_left,
                end=ft.alignment.center_right,
                colors=["#FF6B6B", "#4ECDC4", "#45B7D1"],
            )
            progress_empty.bgcolor = "#E5E7EB"
            progress_bar_container.bgcolor = "#E5E7EB"
            progress_filled.shadow = ft.BoxShadow(
                spread_radius=1,
                blur_radius=8,
                color="#40FF6B6B",
                offset=ft.Offset(0, 0),
            )
        
        progress_filled.update()
        progress_empty.update()
        progress_bar_container.update()
        
        page.update()

    # Layout Construction

    # Sidebar
    sidebar_content = ft.Column([
        ft.Container(
            content=ft.Column([
                ft.Image(src=resource_path("logo.png"), width=80, height=80, fit=ft.ImageFit.CONTAIN) if os.path.exists(resource_path("logo.png")) else ft.Icon("build_circle", size=60, color=LIGHT_ACCENT),
                ft.Text("Montaj Sihirbazı", size=18, weight="bold", text_align="center"),
            ], horizontal_alignment="center"),
            alignment=ft.alignment.center,
            padding=20
        ),
        ft.Divider(color="transparent"),
        ft.Container(
            content=ft.Column([
                ft.Text("KASA YOLU", size=10, weight="bold", color="grey"),
                ft.Container(
                    content=ft.Row([
                        ft.Icon("folder", size=16, color="grey"),
                        vault_path_text
                    ]),
                    padding=10,
                    bgcolor="#0D000000",
                    border_radius=10,
                    on_click=lambda _: file_picker.get_directory_path(),
                    tooltip="Kasa Yolu Seç"
                )
            ]),
        ),
        ft.Divider(color="transparent"),
        ft.Container(
            content=ft.Column([
                ft.Text("MONTAJ SEÇENEĞİ", size=10, weight="bold", color="grey"),
                ft.Row([
                    add_to_existing_checkbox,
                    ft.Text("Mevcut montaja ekle", size=12)
                ], spacing=5, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row([
                    stop_on_not_found_checkbox,
                    ft.Text("Bulunamayan varsa durdur", size=12)
                ], spacing=5, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row([
                    dedupe_codes_checkbox,
                    ft.Text("Aynı kodu bir kere aç", size=12)
                ], spacing=5, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ], spacing=5),
        ),
        ft.Container(expand=True),
        ft.Row([
            ft.IconButton(content=theme_icon, on_click=toggle_theme, tooltip="Temayı Değiştir"),

        ], alignment="center")
    ])

    sidebar_card = ModernCard(sidebar_content, width=250)

    # Header
    header_content = ft.Row([
        ft.Column([
            ft.Text("PDM Montaj Sihirbazı", size=20, weight="bold"),
            ft.Text("Otomatik montaj ve doğrulama sistemi", size=12, color="grey"),
        ]),
        ft.Container(
            content=ft.Row([ft.Icon("check_circle", size=16, color="green"), status_text], spacing=5),
            padding=ft.padding.symmetric(horizontal=15, vertical=8),
            border_radius=20,
            bgcolor="#1A008000"
        )
    ], alignment="spaceBetween")
    
    header_card = ModernCard(header_content)

    # Input Area
    input_field = ft.TextField(
        multiline=True, min_lines=10, max_lines=10,
        hint_text="SAP Kodlarını buraya yapıştırın...",
        border=ft.InputBorder.OUTLINE,
        border_radius=15,
        text_style=ft.TextStyle(font_family="Consolas", size=14),
        filled=True,
        bgcolor="#05000000",
        border_color="transparent"
    )
    
    def clear_click(e):
        input_field.value = ""
        log_lines.controls.clear()
        processed_count.value = "0"
        success_count.value = "0"
        error_count.value = "0"
        progress_filled.expand = 0
        progress_empty.expand = 100
        status_text.value = "Hazır"
        not_found_codes_list.clear()
        copy_button.visible = False
        
        input_field.update()
        log_lines.update()
        processed_count.update()
        success_count.update()
        error_count.update()
        progress_bar_widget.update()
        status_text.update()
        copy_button.update()

    def cancel_click(e):
        if logic.is_running:
            logic.stop_process()
            add_log("İşlem kullanıcı tarafından iptal edildi.", "#f59e0b")

    def start_click(e):
        # Check if vault path is set
        if not logic.vault_path:
            add_log("Lütfen kasa yolu giriniz.", "#ef4444")
            return
        
        codes = [line.strip() for line in input_field.value.splitlines() if line.strip()]
        if dedupe_codes_checkbox.value and codes:
            unique_codes = list(dict.fromkeys(codes))
            if len(unique_codes) != len(codes):
                add_log(f"Tekrarlı kodlar çıkarıldı: {len(codes) - len(unique_codes)} adet", "#6b7280")
            codes = unique_codes
        if not codes:
            return
        
        # Clear previous not found codes
        not_found_codes_list.clear()
        copy_button.visible = False
        copy_button.update()
        
        # Set total count to number of SAP codes
        processed_count.value = str(len(codes))
        success_count.value = "0"
        error_count.value = "0"
        processed_count.update()
        success_count.update()
        error_count.update()
        
        threading.Thread(target=logic.run_process, args=(codes,), daemon=True).start()

    input_content = ft.Column([
        ft.Row([
            ft.Container(content=ft.Icon("tune", color="white", size=16), bgcolor=LIGHT_ACCENT, padding=8, border_radius=8),
            ft.Text("Girdi Parametreleri", size=16, weight="bold")
        ], spacing=10),
        ft.Divider(height=10, color="transparent"),
        input_field,
        ft.Divider(height=10, color="transparent"),
        progress_bar_container,
        ft.Container(expand=True), # Push buttons down
        ft.Column([
            ModernButton(
                "MONTAJI BAŞLAT", 
                "play_arrow", 
                start_click,
                LIGHT_ACCENT,
                border_radius=ft.border_radius.only(top_left=24, top_right=24, bottom_left=12, bottom_right=12)
            ),
            ft.Row([
                ModernButton(
                    "TEMİZLE", 
                    "cleaning_services", 
                    clear_click,
                    "#9E9E9E",
                    expand=True,
                    border_radius=ft.border_radius.only(top_left=12, top_right=12, bottom_left=24, bottom_right=12)
                ),
                ModernButton(
                    "İPTAL", 
                    "stop", 
                    cancel_click,
                    "#EF4444",
                    expand=True,
                    border_radius=ft.border_radius.only(top_left=12, top_right=12, bottom_left=12, bottom_right=24)
                ),
            ], spacing=15, alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        ], spacing=10)
    ])
    
    input_card = ModernCard(input_content, expand=True)

    # Log/Output Area
    card_total = DashboardCard("TOPLAM", processed_count, "format_list_numbered", "#3B82F6")
    card_success = DashboardCard("BAŞARILI", success_count, "check_circle", "#22C55E")
    card_error = DashboardCard("HATA", error_count, "error", "#EF4444")

    log_content = ft.Column([
        ft.Row([
            ft.Container(content=ft.Icon("terminal", color="white", size=16), bgcolor="#6366F1", padding=8, border_radius=8),
            ft.Text("İşlem Terminali", size=16, weight="bold")
        ], spacing=10),
        ft.Divider(height=10, color="transparent"),
        ft.Row([
            card_total,
            card_success,
            card_error,
        ], spacing=10),
        copy_button,  # Add copy button here
        ft.Divider(height=10, color="transparent"),
        ft.Container(
            content=log_lines,
            expand=True,
            bgcolor="#05000000",
            border_radius=10,
            padding=10,
            border=ft.border.all(1, "#1A808080")
        )
    ], expand=True)
    
    log_card = ModernCard(log_content, expand=True)

    # File Picker
    file_picker = ft.FilePicker(on_result=handle_vault_pick)
    page.overlay.append(file_picker)

    # Main Layout
    page.add(
        ft.Row([
            sidebar_card,
            ft.Column([
                header_card,
                ft.Row([input_card, log_card], expand=True, spacing=20)
            ], expand=True, spacing=20)
        ], expand=True, spacing=20)
    )
    
    toggle_theme(None)

if __name__ == "__main__":
    ft.app(target=main)
