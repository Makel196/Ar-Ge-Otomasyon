
import win32com.client
import sys
import subprocess
import time
import threading
import win32gui
import win32con
from tkinter import *
from tkinter import messagebox, scrolledtext

# ==============================================================================
# YARDIMCI FONSİYONLAR
# ==============================================================================

def click_button(hwnd, button_text):
    """Penceredeki belirli bir butona tıklar"""
    try:
        def enum_child_windows(hwnd, result_list):
            def callback(child_hwnd, _):
                result_list.append(child_hwnd)
                return True
            win32gui.EnumChildWindows(hwnd, callback, None)
        
        children = []
        enum_child_windows(hwnd, children)
        
        for child in children:
            try:
                text = win32gui.GetWindowText(child)
                class_name = win32gui.GetClassName(child)
                if button_text.lower() in text.lower() and 'button' in class_name.lower():
                    win32gui.PostMessage(child, win32con.WM_LBUTTONDOWN, 0, 0)
                    win32gui.PostMessage(child, win32con.WM_LBUTTONUP, 0, 0)
                    return True
            except:
                pass
        return False
    except Exception as e:
        return False

def close_sap_popups():
    """SAP Logon uyarı pencerelerini otomatik kapat"""
    def callback(hwnd, extra):
        try:
            title = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)
            if "#32770" in class_name and win32gui.IsWindowVisible(hwnd):
                if "SAP" in title or "Skript" in title or "GUI" in title or "erismeye" in title or len(title) < 30:
                    if click_button(hwnd, "TAMAM") or click_button(hwnd, "OK") or click_button(hwnd, "YES") or click_button(hwnd, "EVET") or click_button(hwnd, "Devam"):
                        # print(f"[OK] SAP popup kapatildi: {title}")
                        return True
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
# SAP BAĞLANTI SINIFI (SapHandler)
# ==============================================================================

class SapHandler:
    def __init__(self):
        self.application = None
        self.connection = None
        self.session = None
        self.SapGuiAuto = None
        
        # Popup kapatıcıyı başlat
        if not any(t.name == "PopupCloser" for t in threading.enumerate()):
            popup_thread = threading.Thread(target=auto_close_popups_thread, daemon=True, name="PopupCloser")
            popup_thread.start()

    def connect_to_sap(self):
        """Mevcut SAP oturumuna bağlanır veya yoksa yeni açar."""
        try:
            # 1. SAP GUI Nesnesini Almayı Dene
            try:
                self.SapGuiAuto = win32com.client.GetObject("SAPGUI")
            except:
                # SAP açık değilse başlat
                print("SAP GUI bulunamadı, başlatılıyor...")
                subprocess.Popen([r"C:\Program Files\SAP\FrontEnd\SAPGUI\saplogon.exe"])
                for i in range(30): # 15 saniye bekle
                    try:
                        self.SapGuiAuto = win32com.client.GetObject("SAPGUI")
                        break
                    except:
                        time.sleep(0.5)
            
            if not self.SapGuiAuto:
                print("SAP GUI nesnesi alınamadı.")
                return False

            # Scripting Engine
            self.application = self.SapGuiAuto.GetScriptingEngine
            self.application.AllowSystemCalls = True
            self.application.HistoryEnabled = False

            # 2. Mevcut Bağlantı/Oturum Kontrolü (Hangi durumdaysa oradan devam et)
            if self.application.Connections.Count > 0:
                # Zaten bir bağlantı varsa ilkini kullan
                self.connection = self.application.Connections.Item(0)
                if self.connection.Sessions.Count > 0:
                    self.session = self.connection.Sessions.Item(0)
                    print("Mevcut SAP oturumu bulundu ve bağlandı.")
            else:
                # Hiç bağlantı yoksa yeni aç
                # Not: Bağlantı adı sisteminizde farklı olabilir
                self.connection = self.application.OpenConnection("1 - POLAT S/4 HANA CANLI (PMP)", True)
                time.sleep(1)
                self.session = self.connection.Children(0)
                print("Yeni SAP bağlantısı açıldı.")

            if self.session:
                # Pencereyi öne getir
                try:
                    self.session.findById("wnd[0]").maximize()
                except:
                    pass
                return True
            
            return False

        except Exception as e:
            print(f"SAP Bağlantı Hatası: {e}")
            return False

    def login(self, username, password):
        """Giriş yapılmamışsa giriş yapar."""
        if not self.session:
            return False
        
        try:
            # Kullanıcı adı alanı varsa giriş ekranındayız demektir
            # SAP ID'leri sistemden sisteme değişebilir, standart olanları deniyoruz
            try:
                user_field = self.session.findById("wnd[0]/usr/txtRSYST-BNAME")
                if user_field:
                    user_field.text = username
                    self.session.findById("wnd[0]/usr/pwdRSYST-BCODE").text = password
                    self.session.findById("wnd[0]/usr/txtRSYST-LANGU").text = "TR"
                    self.session.findById("wnd[0]").sendVKey(0) # Enter
                    print("Giriş işlemi yapıldı.")
                    return True
            except:
                # Kullanıcı alanı bulunamadıysa muhtemelen zaten giriş yapılmıştır
                print("Zaten giriş yapılmış veya giriş ekranı değil.")
                return True
                
        except Exception as e:
            print(f"Login Hatası: {e}")
            return False

    def get_bom_components(self, material_code):
        """CS03 işlem koduna gidip BOM (Ürün Ağacı) bileşenlerini çeker."""
        if not self.session:
            return []

        components = []
        try:
            # Bulunduğumuz yerden CS03'e git (/nCS03 yeni pencere açmadan gider)
            self.session.findById("wnd[0]/tbar[0]/okcd").text = "/nCS03"
            self.session.findById("wnd[0]").sendVKey(0)
            time.sleep(1)

            # Malzeme Kodu Girişi
            try:
                print(f"Malzeme Kodu Giriliyor: {material_code}")
                # Alanları temizle/doldur
                self.session.findById("wnd[0]/usr/ctxtRC29N-MATNR").text = material_code
                self.session.findById("wnd[0]/usr/ctxtRC29N-WERKS").text = "3000" # Fabrika
                self.session.findById("wnd[0]/usr/ctxtRC29N-STLAN").text = "1"    # Kullanım
                self.session.findById("wnd[0]").sendVKey(0) # Enter
            except Exception as e:
                print(f"CS03 Giriş Ekranı Hatası: {e}")
                # Belki hata popup'ı vardır, Enter'a basıp geçmeyi deneyelim
                try: self.session.findById("wnd[0]").sendVKey(0)
                except: pass
                return []
            
            time.sleep(1)

            # Statü bar kontrolü (Hata mesajı var mı?)
            try:
                sbar = self.session.findById("wnd[0]/sbar")
                if sbar.messageType == "E": # Error
                    print(f"SAP Hatası: {sbar.text}")
                    return []
            except:
                pass

            # Tabloyu Okuma
            try:
                # Tablo ID'si genellikle sabittir ama bazen değişebilir
                table = self.session.findById("wnd[0]/usr/subSUB_ALL:SAPLCSDI:3211/tblSAPLCSDITCTRL_3211")
                rows = table.RowCount
                
                print(f"Tablo bulundu, {rows} satır taranıyor...")
                
                for i in range(rows):
                    try:
                        # Hücre verilerini al
                        comp_code = table.GetCell(i, "IDNRK").text.strip() # Bileşen
                        comp_qty = table.GetCell(i, "MENGE").text.strip()  # Miktar
                        comp_desc = table.GetCell(i, "POTX1").text.strip() # Tanım (Opsiyonel)

                        if comp_code:
                            components.append({
                                "code": comp_code,
                                "quantity": comp_qty,
                                "description": comp_desc
                            })
                    except Exception:
                        pass
                        
            except Exception as e:
                print(f"Tablo okuma hatası: {e}")
                # Bazen alternatif ekran veya tab gelebilir, burası genişletilebilir
            
        except Exception as e:
            print(f"BOM Okuma Genel Hatası: {e}")

        return components

# ==============================================================================
# TEST GUI (Standalone Kullanım İçin)
# ==============================================================================

if __name__ == "__main__":
    # Test amaçlı arayüz
    sap_handler = SapHandler()
    
    def gui_login():
        u = entry_user.get()
        p = entry_pass.get()
        if sap_handler.connect_to_sap():
            sap_handler.login(u, p)
            log_msg("Bağlantı ve Login denendi.")
        else:
            log_msg("SAP Bağlantısı Kurulamadı!")

    def gui_get_bom():
        m = entry_material.get()
        if not m:
            log_msg("Malzeme kodu giriniz!")
            return
            
        log_msg(f"BOM çekiliyor: {m}...")
        
        # Eğer bağlantı kopmuşsa tekrar bağlanmayı dene
        if not sap_handler.session:
            if not sap_handler.connect_to_sap():
                log_msg("SAP Bağlantısı yok!")
                return

        comps = sap_handler.get_bom_components(m)
        if comps:
            log_msg(f"BULUNDU: {len(comps)} bileşen")
            output_text.delete(1.0, END)
            for c in comps:
                output_text.insert(END, f"{c['code']} \t| adet: {c['quantity']} \t| {c['description']}\n")
        else:
            log_msg("Bileşen bulunamadı veya hata oluştu.")

    def log_msg(msg):
        print(msg)
        status_label.config(text=msg)

    root = Tk()
    root.title("SAP Entegrasyon Test")
    root.geometry("600x500")

    Frame(root, height=10).pack()

    # Login Alanı
    lf_login = LabelFrame(root, text="Login Bilgileri")
    lf_login.pack(fill=X, padx=10)
    
    Label(lf_login, text="Kullanıcı:").pack(side=LEFT, padx=5)
    entry_user = Entry(lf_login, width=15)
    entry_user.insert(0, "aarslan")
    entry_user.pack(side=LEFT, padx=5)
    
    Label(lf_login, text="Şifre:").pack(side=LEFT, padx=5)
    entry_pass = Entry(lf_login, show="*", width=15)
    entry_pass.insert(0, "Pgr1234567")
    entry_pass.pack(side=LEFT, padx=5)
    
    Button(lf_login, text="Bağlan / Login", command=gui_login).pack(side=LEFT, padx=10)

    Frame(root, height=10).pack()

    # İşlem Alanı
    lf_action = LabelFrame(root, text="BOM Okuma")
    lf_action.pack(fill=X, padx=10)
    
    Label(lf_action, text="Malzeme Kodu:").pack(side=LEFT, padx=5)
    entry_material = Entry(lf_action, width=20)
    entry_material.insert(0, "473501297")
    entry_material.pack(side=LEFT, padx=5)
    
    Button(lf_action, text="Bileşenleri Getir", command=gui_get_bom, bg="#4caf50", fg="white").pack(side=LEFT, padx=10)

    # Çıktı
    output_text = scrolledtext.ScrolledText(root, height=15)
    output_text.pack(fill=BOTH, expand=True, padx=10, pady=10)
    
    status_label = Label(root, text="Hazır", bd=1, relief=SUNKEN, anchor=W)
    status_label.pack(fill=X)

    root.mainloop()
