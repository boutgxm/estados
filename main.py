import json
import csv

# Archivo de entrada
archivo_txt = "Estados.txt"

# Lista donde guardaremos los datos
estados = []

# Leer el archivo CSV
with open(archivo_txt, "r", encoding="utf-8") as file:
    lector = csv.DictReader(file)

    for fila in lector:
        # Convertir números a int
        fila["Temperatura"] = int(fila["Temperatura"])
        fila["Humedad"] = int(fila["Humedad"])
        fila["Costo_Alojamiento"] = int(fila["Costo_Alojamiento"])
        fila["Costo_Transporte"] = int(fila["Costo_Transporte"])
        fila["Dias_Promedio"] = int(fila["Dias_Promedio"])
        fila["Tiempo_Traslado"] = int(fila["Tiempo_Traslado"])

        estados.append(fila)

# Crear estructura final
datos_json = {
    "Estados": estados
}

# Guardar archivo JSON
with open("estados.json", "w", encoding="utf-8") as json_file:
    json.dump(datos_json, json_file, indent=4, ensure_ascii=False)

print("JSON creado correctamente ✅")

