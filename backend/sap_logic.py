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
        time.sleep(1)

# ==============================================================================
# SAP BAĞLANTI SINIFI
# ==============================================================================

class SapGui():
    def __init__(self):
        self.sap_gui_auto = None
        self.application = None
        self.connection = None
        self.session = None
        
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
        """SAP GUI'ye bağlanır veya başlatır."""
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
                return False

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
                    time.sleep(1)
                    self.session = self.connection.Children(0)
                except Exception as e:
                    print(f"Bağlantı açma hatası: {e}")

                    return False

            if self.session:
                try: self.session.AllowSystemCalls = True
                except: pass
                # Pencereyi öne getir
                try: self.session.findById("wnd[0]").maximize()
                except: pass
                return True
            
            return False

        except Exception as e:
            print(f"SAP Genel Bağlantı Hatası: {e}")
            return False

    def sapLogin(self, username, password):
        """Verilen bilgilerle SAP'ye giriş yapar."""
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
            time.sleep(1)

            # Malzeme parametrelerini gir
            try:
                self.session.findById("wnd[0]/usr/ctxtRC29N-MATNR").text = material_code
                self.session.findById("wnd[0]/usr/ctxtRC29N-WERKS").text = "3000" # Fabrika
                self.session.findById("wnd[0]/usr/ctxtRC29N-STLAN").text = "1"    # Kullanım
                self.session.findById("wnd[0]").sendVKey(0)
            except Exception as e:
                print(f"CS03 parametre girme hatası: {e}")
                return []
            
            time.sleep(1.5)
            
            # Hata kontrolü (sol alt köşe)
            try:
                sbar = self.session.findById("wnd[0]/sbar")
                if sbar.messageType == "E":
                    print(f"SAP Mesajı (Hata): {sbar.text}")
                    return []
            except:
                pass

            # Tabloyu Oku
            components = []
            try:
                # Tablo ID'si
                table = self.session.findById("wnd[0]/usr/subSUB_ALL:SAPLCSDI:3211/tblSAPLCSDITCTRL_3211")
                for i in range(table.RowCount):
                    try:
                        comp_code = table.GetCell(i, "IDNRK").text.strip()
                        comp_qty = table.GetCell(i, "MENGE").text.strip()
                        comp_desc = table.GetCell(i, "POTX1").text.strip()

                        if comp_code:
                            components.append({
                                "code": comp_code,
                                "quantity": comp_qty,
                                "description": comp_desc
                            })
                    except:
                        pass
            except Exception as e:
                print(f"Tablo okuma hatası: {e}")
            
            return components

        except Exception as e:
            print(f"BOM okuma geneli hatası: {e}")
            return []
