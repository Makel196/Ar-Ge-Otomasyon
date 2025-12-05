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

def auto_close_popups_thread():
    """Arka planda sürekli çalışan popup kapatıcı thread"""
    while True:
        close_sap_popups()
        time.sleep(0.5)

# ==============================================================================
# SAP BAĞLANTI SINIFI
# ==============================================================================

class SapGui():
    def __init__(self):
        self.sap_gui_auto = None
        self.application = None
        self.connection = None
        self.session = None
        self.retry_mode = True # Kullanıcı isteği: Kesinti olmamalı, internet yoksa sonsuza kadar denemeli
        
        # Popup kapatıcı thread'i başlat
        if not any(t.name == "PopupCloser" for t in threading.enumerate()):
            popup_thread = threading.Thread(target=auto_close_popups_thread, daemon=True, name="PopupCloser")
            popup_thread.start()

        self.connect_to_sap()

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
                    time.sleep(0.5)

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
                        time.sleep(0.5)
                        self.session = self.connection.Children(0)
                    except Exception as e:
                        print(f"Bağlantı açma hatası: {e}")
                        raise e

                if self.session:
                    try: self.session.AllowSystemCalls = True
                    except: pass
                    # Pencereyi öne getir
                    try: self.session.findById("wnd[0]").maximize()
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

    def get_bom_components(self, material_code):
        """CS03 işlem koduna gidip BOM bileşenlerini çeker."""
        if not self.session:
            return []

        try:
            # CS03'e git (/nCS03 yeni işlem başlatır)
            self.session.findById("wnd[0]/tbar[0]/okcd").text = "/nCS03"
            self.session.findById("wnd[0]").sendVKey(0)
            time.sleep(0.5)

            # Malzeme parametrelerini gir
            try:
                self.session.findById("wnd[0]/usr/ctxtRC29N-MATNR").text = material_code
                self.session.findById("wnd[0]/usr/ctxtRC29N-WERKS").text = "3000" # Fabrika
                self.session.findById("wnd[0]/usr/ctxtRC29N-STLAN").text = "1"    # Kullanım
                self.session.findById("wnd[0]").sendVKey(0)
            except Exception as e:
                print(f"CS03 parametre girme hatası: {e}")
                return []
            
            time.sleep(0.5)
            
            # Hata kontrolü (sol alt köşe)
            try:
                sbar = self.session.findById("wnd[0]/sbar")
                if sbar.messageType == "E":
                    print(f"SAP Mesajı (Hata): {sbar.text}")
                    return []
            except:
                pass

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
            
            return components

        except Exception as e:
            print(f"BOM okuma geneli hatası: {e}")
            return []
