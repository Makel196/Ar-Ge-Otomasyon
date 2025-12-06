import win32com.client
import subprocess
import time
import threading
import win32gui
import win32con
import os
import sys

# ==============================================================================
# YARDIMCI FONSİYONLAR
# ==============================================================================

def click_button(hwnd, button_texts):
    """Penceredeki belirli bir butona tıklar"""
    try:
        def enum_child_windows(h, result_list):
            def callback(child_hwnd, _):
                result_list.append(child_hwnd)
                return True
            win32gui.EnumChildWindows(h, callback, None)
        
        children = []
        enum_child_windows(hwnd, children)
        
        for child in children:
            try:
                text = win32gui.GetWindowText(child)
                class_name = win32gui.GetClassName(child)
                
                # Check if it's a button and matches one of the texts
                if 'button' in class_name.lower():
                    for btn_text in button_texts:
                        if btn_text.lower() == text.lower() or btn_text.lower() in text.lower():
                            win32gui.PostMessage(child, win32con.WM_LBUTTONDOWN, 0, 0)
                            win32gui.PostMessage(child, win32con.WM_LBUTTONUP, 0, 0)
                            return True
            except:
                pass
        return False
    except Exception:
        return False

def close_sap_popups():
    """SAP Logon uyarı pencerelerini otomatik kapat"""
    def callback(hwnd, extra):
        try:
            title = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)
            if "#32770" in class_name and win32gui.IsWindowVisible(hwnd):
                # Sık karşılaşılan popup başlıkları
                common_titles = ["SAP", "Skript", "GUI", "Security", "Güvenlik", "erismeye"]
                if any(t in title for t in common_titles) or len(title) < 30:
                    buttons = ["TAMAM", "OK", "YES", "EVET", "Devam", "Allow", "İzin Ver"]
                    if click_button(hwnd, buttons):
                        # print(f"SAP popup kapatildi: {title}")
                        pass
        except:
            pass
        return True
    
    try:
        win32gui.EnumWindows(callback, None)
    except:
        pass

def minimize_sap_logon_window():
    """SAP Logon penceresini minimize eder"""
    def callback(hwnd, _):
        try:
            val = win32gui.GetWindowText(hwnd)
            # Pencere başlığında SAP Logon geçiyorsa (case insensitive)
            if "sap logon" in val.lower() and win32gui.IsWindowVisible(hwnd):
                 # SW_SHOWMINNOACTIVE = 7 (Hem minimize eder hem de focus çalmaz)
                 win32gui.ShowWindow(hwnd, 7)
        except:
            pass
    try:
        win32gui.EnumWindows(callback, None)
    except:
        pass

# Global flag to control popup thread
POPUP_THREAD_RUNNING = True

def auto_close_popups_thread():
    """Arka planda sürekli çalışan popup kapatıcı thread"""
    global POPUP_THREAD_RUNNING
    while POPUP_THREAD_RUNNING:
        close_sap_popups()
        time.sleep(0.1) # CPU kullanımını azaltmak için sleep artırıldı

def keep_sap_alive_thread():
    """SAP Session'ı canlı tutmak için periyodik aktivite (10 dk)."""
    while True:
        time.sleep(600) # 10 dakika bekle
        try:
             # SAP GUI Bağlantısı
             sap_gui = win32com.client.GetObject("SAPGUI")
             application = sap_gui.GetScriptingEngine
             if application.Connections.Count > 0:
                 conn = application.Connections.Item(0)
                 if conn.Sessions.Count > 0:
                     session = conn.Sessions.Item(0)
                     # Session'a 'dokunarak' aktif tut (Enter tuşu - En güvenli ping)
                     try:
                        session.findById("wnd[0]").SendVKey(0)
                        # Ping attıktan sonra popup çıkarsa hemen kapat
                        time.sleep(0.5)
                        close_sap_popups()
                        # Tekrar kontrol (güvenlik için)
                        time.sleep(0.5)
                        close_sap_popups()
                     except:
                        pass
        except:
             # Bağlantı hatası durumunda da popup varsa temizle
             close_sap_popups()

def start_keep_alive_service():
    """SAP Keep-Alive servisini başlatır (Singleton)."""
    if not any(t.name == "SapKeepAlive" for t in threading.enumerate()):
        t = threading.Thread(target=keep_sap_alive_thread, daemon=True, name="SapKeepAlive")
        t.start()

# ==============================================================================
# SAP BAĞLANTI SINIFI
# ==============================================================================

class SapGui():
    def __init__(self):
        self.sap_gui_auto = None
        self.application = None
        self.connection = None
        self.session = None
        self.retry_mode = True 
        
        # Popup kapatıcı thread'i başlat (Global kontrol)
        global POPUP_THREAD_RUNNING
        POPUP_THREAD_RUNNING = True
        
        if not any(t.name == "PopupCloser" and t.is_alive() for t in threading.enumerate()):
            popup_thread = threading.Thread(target=auto_close_popups_thread, daemon=True, name="PopupCloser")
            popup_thread.start()

        self.connect_to_sap()
    
    def stop_popup_blocker(self):
        """Popup engelleyiciyi durdurur."""
        global POPUP_THREAD_RUNNING
        POPUP_THREAD_RUNNING = False

    def find_sap_path(self):
        """SAP Logon yolunu bulur."""
        possible_paths = [
            os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "SAP\\FrontEnd\\SAPgui\\saplogon.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "SAP\\FrontEnd\\SAPgui\\saplogon.exe")
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return None

    def connect_to_sap(self):
        """SAP GUI'ye bağlanır veya başlatır. Hata durumunda sonsuz dener."""
        while True:
            try:
                # 1. Mevcut SAP nesnesini almayı dene
                try:
                    self.sap_gui_auto = win32com.client.GetObject("SAPGUI")
                except:
                    # Çalışmıyorsa başlat
                    sap_path = self.find_sap_path()
                    if sap_path:
                        try:
                            subprocess.Popen([sap_path])
                            # print("SAP Logon başlatılıyor...")
                        except Exception as e:
                            print(f"SAP Logon başlatılamadı: {e}")
                    else:
                        print("SAP yolu bulunamadı.")

                 # Nesnenin gelmesini bekle
                max_wait = 30
                for i in range(max_wait):
                    try:
                        self.sap_gui_auto = win32com.client.GetObject("SAPGUI")
                        if type(self.sap_gui_auto) == win32com.client.CDispatch:
                            break
                    except:
                        pass
                    time.sleep(0.1)

                if not self.sap_gui_auto:
                    raise Exception("SAPGUI nesnesi gelmedi")

                self.application = self.sap_gui_auto.GetScriptingEngine
                
                # Ayarlar (Scripting izni vb.)
                try: self.application.AllowSystemCalls = True
                except: pass
                try: self.application.HistoryEnabled = False
                except: pass

                # 2. Bağlantı Yönetimi
                if self.application.Connections.Count > 0:
                    # Halihazırda açık bir bağlantı varsa
                    self.connection = self.application.Connections.Item(0)
                    if self.connection.Sessions.Count > 0:
                        self.session = self.connection.Sessions.Item(0)
                else:
                    # Yoksa yeni bağlantı aç
                    try:
                        self.connection = self.application.OpenConnection("1 - POLAT S/4 HANA CANLI (PMP)", True)
                        time.sleep(0.1)
                        self.session = self.connection.Children(0)
                    except Exception as e:
                        print(f"Bağlantı açma hatası: {e}")
                        raise e

                if self.session:
                    try: self.session.AllowSystemCalls = True
                    except: pass
                    
                    # Logon penceresini minimize et (tekrarlı ve thread içinde)
                    minimize_sap_logon_window()
                    def minimize_loop():
                        import time
                        for _ in range(10): # 10 saniye boyunca dene
                            minimize_sap_logon_window()
                            time.sleep(1)
                    threading.Thread(target=minimize_loop, daemon=True).start()
                    
                    # Pencereyi minimize et
                    try: self.session.findById("wnd[0]").iconify()
                    except: pass
                    return True
                
                raise Exception("Session oluşturulamadı")

            except Exception as e:
                print(f"SAP Bağlantı Hatası: {e}")
                if self.retry_mode:
                    print("Bağlantı sağlanamadı. 60 saniye sonra tekrar denenecek...")
                    time.sleep(60)
                else:
                    return False

    def sapLogin(self, username, password):
        """Verilen bilgilerle SAP'ye giriş yapar ve çoklu oturum uyarısını yönetir."""
        if not self.session:
            return False
            
        try:
            # Giriş ekranında mıyız kontrol et (Kullanıcı adı alanı var mı?)
            try:
                self.session.findById("wnd[0]/usr/txtRSYST-MANDT").text = "400"
                self.session.findById("wnd[0]/usr/txtRSYST-BNAME").text = username
                self.session.findById("wnd[0]/usr/pwdRSYST-BCODE").text = password
                self.session.findById("wnd[0]/usr/txtRSYST-LANGU").text = "TR"
                self.session.findById("wnd[0]").sendVKey(0) # Enter
                
                # ÇOKLU OTURUM KONTROLÜ (Multiple Logon)
                # wnd[1] genelde popup penceresidir
                try:
                    # Eğer birden çok oturum penceresi çıkarsa
                    # Metin: "Bu oturum ile devam et ve tüm açık oturumları kapat" (Option 1)
                    # Genellikle radyo butonu ID'si: wnd[1]/usr/radMULTI_LOGON_OPT1
                    if self.session.findById("wnd[1]"):
                        # Radyo butonunu seç
                        try:
                            self.session.findById("wnd[1]/usr/radMULTI_LOGON_OPT1").select()
                            self.session.findById("wnd[1]").sendVKey(0) # Enter
                            print("Çoklu oturum uyarısı: Diğer oturumlar kapatılarak devam edildi.")
                        except:
                            pass
                except:
                    pass

                return True
            except:
                # Alan yoksa muhtemelen zaten giriş yapılmıştır
                print("Giriş ekranı değil veya zaten giriş yapılmış.")
                return True
        except Exception as e:
            print(f"Login Hatası: {e}")

            return False

    def _smart_find_field(self, field_name, field_type_guess="GuiCTextField"):
        """Ekran üzerindeki bir alanı ismiyle (örn: RC29K-MATNR) akıllıca arar."""
        try:
            user_area = self.session.findById("wnd[0]/usr")
            # 1. Doğrudan ismi ve tipi ile ara
            try:
                found_item = user_area.FindByName(field_name, field_type_guess)
                if found_item:
                    return found_item.Text
            except:
                pass
            
            # 2. Tip tutmazsa diğer tipleri dene
            alt_types = ["GuiTextField", "GuiCTextField", "GuiLabel", "GuiStatusPane"]
            for f_type in alt_types:
                if f_type == field_type_guess: continue
                try:
                    found_item = user_area.FindByName(field_name, f_type)
                    if found_item:
                        return found_item.Text
                except:
                    pass
        except:
            pass
        return None

    def get_bom_components(self, material_code):
        """CS03 işlem koduna gidip BOM bileşenlerini çeker."""
        if not self.session:
            return {'header': None, 'components': []}

        try:
            # Ensure minimized
            try: self.session.findById("wnd[0]").iconify()
            except: pass
            # CS03'e git (/nCS03 yeni işlem başlatır)
            self.session.findById("wnd[0]/tbar[0]/okcd").text = "/nCS03"
            self.session.findById("wnd[0]").sendVKey(0)
            time.sleep(0.1)

            # Malzeme parametrelerini gir
            try:
                self.session.findById("wnd[0]/usr/ctxtRC29N-MATNR").text = material_code
                self.session.findById("wnd[0]/usr/ctxtRC29N-WERKS").text = "3000" # Fabrika
                self.session.findById("wnd[0]/usr/ctxtRC29N-STLAN").text = "1"    # Kullanım
                self.session.findById("wnd[0]").sendVKey(0)
            except Exception as e:
                print(f"CS03 parametre girme hatası: {e}")
                return {'header': None, 'components': []}
            
            time.sleep(0.1)
            
            # Hata kontrolü (sol alt köşe)
            try:
                sbar = self.session.findById("wnd[0]/sbar")
                if sbar.messageType == "E":
                    print(f"SAP Mesajı (Hata): {sbar.text}")
                    return {'header': None, 'components': []}
            except:
                pass
            
            # --- BAŞLIK BİLGİLERİNİ OKU (AKILLI MOD) ---
            target_matnr_name = "RC29K-MATNR"
            target_desc_name  = "RC29K-OBKTX"

            # 1. Akıllı Arama ile Bul
            header_matnr = self._smart_find_field(target_matnr_name, "GuiCTextField")
            header_desc = self._smart_find_field(target_desc_name, "GuiTextField")

            # 2. Bulunamazsa Yedekler (Fallback)
            if not header_matnr:
                header_matnr = self._smart_find_field("RC29N-MATNR", "GuiCTextField") 

            if not header_matnr:
                # Pencere başlığından yakalama
                try:
                    title = self.session.findById("wnd[0]").Text
                    if ":" in title:
                        parts = title.split(":")
                        if len(parts) > 1:
                            potential_mat = parts[1].strip().split(" ")[0]
                            if len(potential_mat) > 3:
                                header_matnr = potential_mat
                except:
                    pass
            
            if not header_matnr or not header_matnr.strip():
                header_matnr = "BULUNAMADI"

            if not header_desc:
                header_desc = self._smart_find_field("RC29N-MATTX", "GuiTextField")

            if not header_desc:
                header_desc = ""

            header_info = {
                "material": header_matnr,
                "description": header_desc
            }

            # Tabloyu Oku ve Logla
            components = []
            try:
                table = None
                # Dinamik Tablo Bulma (Recursive)
                def find_table(container):
                    try:
                        if container.Children.Count > 0:
                            for i in range(container.Children.Count):
                                child = container.Children.Item(i)
                                if child.Type == "GuiTableControl":
                                    return child
                                # Recursive arama (Tabstrip, Subscreen vb. içini tara)
                                found = find_table(child)
                                if found: return found
                    except:
                        pass
                    return None

                # Tablo Bulma Stratejisi
                user_table_id = r"wnd[0]/usr/tabsTS_ITOV/tabpTCMA/ssubSUBPAGE:SAPLCSDI:0152/tblSAPLCSDITCMAT"
                
                def get_table_object():
                    # 1. Öncelik: Kullanıcının verdiği sabit ID
                    try:
                        return self.session.findById(user_table_id)
                    except:
                        pass
                    
                    # 2. Öncelik: Dinamik Arama
                    try:
                        usr_area = self.session.findById("wnd[0]/usr")
                        t = find_table(usr_area)
                        if t: return t
                    except:
                        pass
                        
                    # 3. Öncelik: Eski fallback ID (Gerekirse)
                    try:
                        return self.session.findById("wnd[0]/usr/subSUB_ALL:SAPLCSDI:3211/tblSAPLCSDITCTRL_3211")
                    except:
                        return None

                table = get_table_object()

                if table:
                    # --- Sütun Ayarları (Kullanıcının kodundan) ---
                    col_idx_comp = 2            # Bileşen No Varsayılan
                    col_idx_desc = -1           # Tanım
                    col_idx_menge = -1          # Miktar
                    
                    col_name_desc_target = "KTEXT"
                    col_name_menge_target = "MENGE"

                    # Sütun indekslerini bul
                    try:
                        for i in range(table.Columns.Count):
                            col_name = table.Columns.ElementAt(i).Name
                            if col_name_desc_target in col_name:
                                col_idx_desc = i
                            if col_name_menge_target in col_name:
                                col_idx_menge = i
                    except:
                        pass

                    if col_idx_desc == -1: col_idx_desc = 3
                    if col_idx_menge == -1: col_idx_menge = 4

                    # --- Hız ve Scroll Parametreleri ---
                    delay_scroll = 0.15 
                    delay_retry = 0.05
                    
                    total_rows = table.RowCount 
                    visible_rows = table.VisibleRowCount 
                    
                    # Scroll başa al
                    try:
                        table.verticalScrollbar.position = 0
                    except:
                        pass
                    
                    current_row = 0
                    stop_execution = False
                    
                    # --- ANA DÖNGÜ (Scrolling) ---
                    while current_row < total_rows:
                        if stop_execution:
                            break
                        
                        # 1. Scroll İşlemi
                        try:
                            table.verticalScrollbar.position = current_row
                        except:
                            table = get_table_object()
                            if table:
                                try:
                                    table.verticalScrollbar.position = current_row
                                except:
                                    break
                            else:
                                break
                        
                        time.sleep(delay_scroll)
                        
                        table = get_table_object()
                        if not table: break
                        
                        rows_remaining = total_rows - current_row
                        rows_to_read_now = min(visible_rows, rows_remaining)
                        
                        for i in range(rows_to_read_now):
                            val_comp = ""
                            val_desc = ""
                            val_menge = ""
                            
                            # 1. Bileşen No
                            try:
                                val_comp = table.GetCell(i, col_idx_comp).Text
                            except:
                                time.sleep(delay_retry)
                                try:
                                    table = get_table_object()
                                    val_comp = table.GetCell(i, col_idx_comp).Text
                                except:
                                    val_comp = ""
                            
                            # Hızlı çıkış kontrolü
                            if not val_comp or not val_comp.strip():
                                stop_execution = True
                                break
                                
                            val_comp = val_comp.lstrip("0")
                            
                            # 2. Bileşen Tanımı
                            try:
                                val_desc = table.GetCell(i, col_idx_desc).Text
                            except:
                                val_desc = ""
                                
                            # 3. Miktar
                            try:
                                val_menge = table.GetCell(i, col_idx_menge).Text
                            except:
                                val_menge = ""
                            
                            # Listeye ekle
                            components.append({
                                "code": val_comp,
                                "quantity": val_menge,
                                "description": val_desc
                            })
                        
                        current_row += rows_to_read_now

                else:
                    print("BOM Tablosu (GuiTableControl) ekranda bulunamadı!")

            except Exception as e:
                print(f"Tablo okuma hatası: {e}")
            
            return {'header': header_info, 'components': components}

        except Exception as e:
            print(f"BOM okuma geneli hatası: {e}")
            return {'header': None, 'components': []}
