import win32com.client
import time
import os

def debug_float_logic():
    print("SolidWorks'e bağlanılıyor...", flush=True)
    try:
        sw_app = win32com.client.GetActiveObject("SldWorks.Application")
    except Exception as e:
        print(f"SolidWorks bulunamadı: {e}")
        return

    print("Aktif doküman alınıyor...", flush=True)
    model = sw_app.ActiveDoc
    if not model:
        print("Açık doküman yok.")
        return

    if model.GetType() != 2: # swDocASSEMBLY
        print("Aktif doküman bir montaj değil.")
        return

    print(f"Montaj: {model.GetTitle()}")
    
    # Get all top-level components
    print("Bileşenler okunuyor...", flush=True)
    comps = model.GetComponents(True)
    
    if not comps:
        print("Montajda bileşen bulunamadı.")
        return

    print(f"Toplam {len(comps)} bileşen bulundu.", flush=True)
    
    fixed_count = 0
    floated_count = 0
    
    for i, comp in enumerate(comps):
        name = comp.Name2
        is_fixed = False
        try:
            is_fixed = comp.IsFixed
        except:
            print(f"  [{i}] {name}: IsFixed okunamadı.")
            continue
            
        status = "SABİT (FIXED)" if is_fixed else "SERBEST (FLOAT)"
        print(f"  [{i}] {name}: {status}")
        
        if is_fixed:
            fixed_count += 1
            print(f"    -> Float yapılıyor...", end="")
            try:
                # Yöntem 1: IsFixed property
                comp.IsFixed = False
                print(" OK (Yöntem 1)")
                floated_count += 1
            except Exception as e1:
                print(f" HATA (Yöntem 1: {e1})")
                try:
                    # Yöntem 2: SetFixedState2 (Eski API)
                    # Not: Bu metod bazen çalışmayabilir ama deneyelim
                    # comp.SetFixedState2(False) 
                    # SolidWorks API dokümanına göre IComponent2::IsFixed read/write'dır.
                    pass
                except Exception as e2:
                    print(f"    -> Yöntem 2 de başarısız: {e2}")

            # Kontrol et
            if not comp.IsFixed:
                 print(f"    -> Başarılı! Yeni durum: SERBEST")
            else:
                 print(f"    -> BAŞARISIZ! Hala SABİT.")

    if floated_count > 0:
        print("Rebuild yapılıyor...")
        model.EditRebuild3()
        print("Tamamlandı.")
    else:
        print("Değişiklik yapılmadı.")

if __name__ == "__main__":
    debug_float_logic()
