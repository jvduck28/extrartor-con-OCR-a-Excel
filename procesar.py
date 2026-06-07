# -*- coding: utf-8 -*-
import os
import sys
import re
import traceback
from datetime import datetime

try:
    import pandas as pd
    import fitz  # PyMuPDF
    from PIL import Image
    import numpy as np
    import openpyxl
    print("✅ Librerías base OK")
except ImportError as e:
    print(f"❌ Error: {e}")
    input("Presioná ENTER para salir...")
    sys.exit(1)

OCR_DISPONIBLE = False
try:
    import easyocr
    OCR_DISPONIBLE = True
    print("✅ EasyOCR detectado")
except ImportError:
    print("⚠️ EasyOCR no instalado.")

# =========================
# CONFIGURACIÓN DE CATEGORÍAS
# =========================
CATEGORIAS = {
    "Servicios": ["luz", "agua", "gas", "edenor", "edesur", "aysa", "metrogas", "telecom", "epec", "claro", "personal", "movistar", "farmacia", "pago de servicios", "pago de servicio"],
    "Inversiones": ["rendimientos", "intereses", "rendimiento"],
    "Ventas/Entradas": ["liquidación de dinero", "liquidación", "acreditacion", "deposito", "haberes", "sueldo"],
    "Transferencias": ["transferencia enviada", "transferencia recibida", "enviada", "recibida"],
    "Compras": ["compra", "pago con qr", "mercadopago", "pago a", "pago farmacia", "pago carrefour"],
    "Otros": []
}

# =========================
# UTILIDADES
# =========================
def normalizar_para_fecha(s):
    s = str(s).upper()
    reemplazos = {"O": "0", "Q": "0", "L": "1", "I": "1", "|": "1", "S": "5", "J": "3"}
    for malo, bueno in reemplazos.items():
        s = s.replace(malo, bueno)
    return s

def convertir_monto(monto_str):
    if not monto_str: return 0.0
    # Ejemplo entrada: "$ -1.014.678,62" o "$ 2.790,00"
    s = str(monto_str).replace("$", "").replace(" ", "").strip()
    if not s: return 0.0
    
    es_negativo = "-" in s
    # Quitamos todo lo que no sea numero o coma
    # El punto de miles lo eliminamos, la coma la pasamos a punto
    s = s.replace("-", "")
    s = s.replace(".", "") # Eliminar puntos de miles
    s = s.replace(",", ".") # Cambiar coma decimal por punto
    
    try:
        val = float(s)
        return -val if es_negativo else val
    except:
        return 0.0

def clasificar(desc):
    desc = desc.lower()
    for cat, keywords in CATEGORIAS.items():
        for k in keywords:
            if k in desc: return cat
    return "Otros"

# ==========================================
# PROCESADOR
# ==========================================
def procesar_planilla(ruta_pdf):
    doc = fitz.open(ruta_pdf)
    movimientos_finales = []
    movimiento_actual = None
    
    for page_idx, page in enumerate(doc):
        print(f"🔎 Analizando página {page_idx + 1}...")
        tokens = []
        w, h = page.rect.width, page.rect.height
        
        words = page.get_text("words") 
        if len(words) > 10: 
            for (x0, y0, x1, y1, text, block_no, line_no, word_no) in words:
                x_center = (x0 + x1) / 2
                xr = x_center / w
                # Ajuste de columnas según posición horizontal
                if xr < 0.15: col = "fecha"
                elif xr < 0.42: col = "concepto"
                elif xr < 0.65: col = "id_op"
                elif xr < 0.86: col = "importe"
                else: col = "saldo"
                tokens.append({"x": x_center, "y": (y0 + y1) / 2, "col": col, "texto": text})
        
        elif OCR_DISPONIBLE:
            pix = page.get_pixmap(dpi=200)
            img_np = np.array(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
            reader = easyocr.Reader(["es"], gpu=False)
            resultados = reader.readtext(img_np)
            for (bbox, text, conf) in resultados:
                xs = [p[0] for p in bbox]
                x_c = sum(xs)/4
                xr = x_c / pix.width
                if xr < 0.15: col = "fecha"
                elif xr < 0.42: col = "concepto"
                elif xr < 0.65: col = "id_op"
                elif xr < 0.86: col = "importe"
                else: col = "saldo"
                tokens.append({"x": x_c, "y": sum([p[1] for p in bbox])/4, "col": col, "texto": text})

        if not tokens: continue

        tokens.sort(key=lambda t: t["y"])
        lineas = []
        for t in tokens:
            if not lineas or abs(lineas[-1]["y"] - t["y"]) > 8:
                lineas.append({"y": t["y"], "tokens": [t]})
            else:
                lineas[-1]["tokens"].append(t)

        for linea in lineas:
            d = {"fecha":[], "concepto":[], "id_op":[], "importe":[], "saldo":[]}
            for t in sorted(linea["tokens"], key=lambda x: x["x"]):
                d[t["col"]].append(t["texto"])
            
            txt_fecha = "".join(d["fecha"])
            match_fecha = re.search(r"(\d{2})[-/](\d{2})[-/](\d{4})", normalizar_para_fecha(txt_fecha))
            
            if match_fecha:
                if movimiento_actual:
                    movimientos_finales.append(movimiento_actual)
                
                fecha_dt = datetime.strptime(match_fecha.group(), "%d-%m-%Y" if "-" in match_fecha.group() else "%d/%m/%Y")
                movimiento_actual = {
                    "fecha": fecha_dt,
                    "descripcion": " ".join(d["concepto"]),
                    "id_operacion": " ".join(d["id_op"]),
                    "importe": convertir_monto(" ".join(d["importe"])),
                    "saldo": convertir_monto(" ".join(d["saldo"]))
                }
            else:
                if movimiento_actual:
                    desc_extra = " ".join(d["concepto"])
                    if desc_extra:
                        movimiento_actual["descripcion"] += " " + desc_extra
                    
                    # Si el importe o saldo no se capturaron en la linea de la fecha, probar capturarlos ahora
                    if movimiento_actual["importe"] == 0 and d["importe"]:
                        movimiento_actual["importe"] = convertir_monto(" ".join(d["importe"]))
                    if movimiento_actual["saldo"] == 0 and d["saldo"]:
                        movimiento_actual["saldo"] = convertir_monto(" ".join(d["saldo"]))

    if movimiento_actual:
        movimientos_finales.append(movimiento_actual)

    doc.close()

    lista_para_excel = []
    for m in movimientos_finales:
        desc_limpia = m["descripcion"].strip()
        if len(desc_limpia) < 2 or "Fecha" in desc_limpia: continue
        
        imp = m["importe"]
        
        lista_para_excel.append({
            "Fecha": m["fecha"].strftime("%d/%m/%Y"),
            "Categoría": clasificar(desc_limpia),
            "Descripción": desc_limpia,
            "ID Operación": re.sub(r"[^0-9]", "", m["id_operacion"]),
            "Débito": abs(imp) if imp < 0 else 0,
            "Crédito": imp if imp > 0 else 0,
            "Valor Neto": imp,
            "Saldo": m["saldo"]
        })
        
    return lista_para_excel

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ No se detectó archivo.")
    else:
        ruta = sys.argv[1]
        try:
            datos = procesar_planilla(ruta)
            if datos:
                df = pd.DataFrame(datos)
                ruta_excel = ruta.replace(".pdf", "_PROCESADO.xlsx")
                # Reordenar columnas para mejor lectura
                df = df[["Fecha", "Categoría", "Descripción", "ID Operación", "Débito", "Crédito", "Valor Neto", "Saldo"]]
                df.to_excel(ruta_excel, index=False)
                print(f"✅ ¡ÉXITO! Guardado en:\n{ruta_excel}")
        except Exception:
            traceback.print_exc()
    input("Presioná ENTER para salir...")