import win32com.client
import subprocess
import time
import threading
import win32gui
import win32con
import os
import sys

class SapHandler:
    def __init__(self):
        self.sap_gui_auto = None
        self.application = None
        self.connection = None
        self.session = None

    def find_sap_path(self):
        """Finds the saplogon.exe path by checking common locations."""
        possible_paths = [
            os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "SAP\\FrontEnd\\SAPgui\\saplogon.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "SAP\\FrontEnd\\SAPgui\\saplogon.exe")
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return None

    def click_button_by_text(self, hwnd, button_texts):
        """Clicks a button in a window if its text matches one of the provided texts."""
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

    def close_sap_popups(self):
        """Closes SAP Logon warning popups automatically."""
        def callback(hwnd, extra):
            try:
                title = win32gui.GetWindowText(hwnd)
                class_name = win32gui.GetClassName(hwnd)
                if "#32770" in class_name and win32gui.IsWindowVisible(hwnd):
                    # Check common popup titles or generic small windows
                    common_titles = ["SAP", "Skript", "GUI", "Security", "Güvenlik", "erismeye"]
                    if any(t in title for t in common_titles) or len(title) < 30:
                        buttons = ["TAMAM", "OK", "YES", "EVET", "Devam", "Allow", "İzin Ver"]
                        if self.click_button_by_text(hwnd, buttons):
                            print(f"SAP popup kapatildi: {title}")
            except:
                pass
            return True
        
        try:
            win32gui.EnumWindows(callback, None)
        except:
            pass

    def auto_close_popups_thread(self):
        """Runs the popup closer in a loop."""
        while True:
            self.close_sap_popups()
            time.sleep(1)

    def connect_to_sap(self):
        """Launches SAP Logon and connects to the running instance."""
        # Check if already running
        try:
            win32com.client.GetObject("SAPGUI")
        except:
            # Not running, try to launch
            sap_path = self.find_sap_path()
            if sap_path:
                try:
                    subprocess.Popen([sap_path])
                    print("SAP Logon başlatılıyor...")
                except Exception as e:
                    print(f"SAP Logon başlatılamadı: {e}")
                    return False
            else:
                print("saplogon.exe bulunamadı. Lütfen SAP'nin kurulu olduğundan emin olun.")
                # Try launching simply by name just in case it is in PATH
                try:
                    subprocess.Popen(["saplogon.exe"])
                except:
                    return False

        # Start popup closer
        threading.Thread(target=self.auto_close_popups_thread, daemon=True).start()

        # Wait for SAP Object
        max_wait = 30
        for i in range(max_wait):
            try:
                self.sap_gui_auto = win32com.client.GetObject("SAPGUI")
                if type(self.sap_gui_auto) == win32com.client.CDispatch:
                    break
            except:
                pass
            time.sleep(1)
            
        if not self.sap_gui_auto:
            print("SAPGUI nesnesi alınamadı.")
            return False

        try:
            self.application = self.sap_gui_auto.GetScriptingEngine
            self.application.AllowSystemCalls = True
            # Checking connection - connect to specific system
            # Note: Assuming connection name is provided or we pick the first one/active one
            # The prompt used "1 - POLAT S/4 HANA CANLI (PMP)", might need to be configurable
            self.connection = self.application.OpenConnection("1 - POLAT S/4 HANA CANLI (PMP)", True)
            time.sleep(1)
            self.session = self.connection.Children(0)
            self.session.findById("wnd[0]").maximize()
            return True
        except Exception as e:
            print(f"SAP bağlantı hatası: {e}")
            return False

    def login(self, username, password):
        """Performs SAP login with provided credentials."""
        if not self.session:
            return False
            
        try:
            self.session.findById("wnd[0]/usr/txtRSYST-MANDT").text = "400"
            self.session.findById("wnd[0]/usr/txtRSYST-BNAME").text = username
            self.session.findById("wnd[0]/usr/pwdRSYST-BCODE").text = password
            self.session.findById("wnd[0]/usr/txtRSYST-LANGU").text = "TR"
            self.session.findById("wnd[0]").sendVKey(0) # Enter
            return True
        except Exception as e:
            print(f"Login hatası: {e}")
            return False

    def get_bom_components(self, material_code):
        """Runs CS03 to get BOM components."""
        if not self.session:
            return []

        try:
            # Go to CS03
            self.session.findById("wnd[0]/tbar[0]/okcd").text = "/nCS03"
            self.session.findById("wnd[0]").sendVKey(0)
            time.sleep(1)

            # Enter Material Params
            try:
                self.session.findById("wnd[0]/usr/ctxtRC29N-MATNR").text = material_code
                self.session.findById("wnd[0]/usr/ctxtRC29N-WERKS").text = "3000" # Plant
                self.session.findById("wnd[0]/usr/ctxtRC29N-STLAN").text = "1"    # Usage
                self.session.findById("wnd[0]").sendVKey(0)
            except Exception as e:
                print(f"CS03 giriş hatası: {e}")
                return []
            
            time.sleep(1.5)
            
            # Check for errors in status bar
            try:
                sbar = self.session.findById("wnd[0]/sbar")
                if sbar.messageType == "E":
                    print(f"SAP Hatası: {sbar.text}")
                    return []
            except:
                pass

            # Read Table
            components = []
            try:
                # Try to find the table - ID might vary but usually consistent
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
