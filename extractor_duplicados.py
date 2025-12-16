import os

# Nombre del archivo de entrada (generado en el paso anterior)
archivo_entrada = "claro_urls.txt"
# Nombre del nuevo archivo de salida
archivo_salida = "urls_a_eliminar.txt" 

# Sufijos a buscar. Se usa una tupla para la función endswith()
sufijos_duplicados = ('_test', '-test', '_1')

def extraer_urls_duplicadas(archivo_entrada, archivo_salida, sufijos):
    """
    Lee un archivo de URLs y extrae aquellas que terminan con sufijos específicos.
    """
    try:
        urls_duplicadas = []

        # 1. Leer las URLs del archivo de entrada
        with open(archivo_entrada, 'r', encoding='utf-8') as f:
            for linea in f:
                url_original = linea.strip()

                if not url_original:
                    continue # Saltar líneas vacías

                # 2. Limpiar la URL de la barra diagonal final (trailing slash) 
                # para que la comprobación de sufijos funcione correctamente
                url_sin_slash = url_original.rstrip('/')
                
                # 3. Comprobar si la URL (sin slash final) termina con alguno de los sufijos
                # La función endswith() acepta una tupla de sufijos para verificar múltiples condiciones.
                if url_sin_slash.endswith(sufijos):
                    urls_duplicadas.append(url_original)

        # 4. Escribir las URLs encontradas en el archivo de salida
        if urls_duplicadas:
            with open(archivo_salida, 'w', encoding='utf-8') as f:
                # Escribimos cada URL en una línea separada, asegurando que termine con un salto de línea.
                f.write('\n'.join(urls_duplicadas) + '\n')

            print(f"✅ Se han encontrado y guardado {len(urls_duplicadas)} URLs a eliminar en '{archivo_salida}'.")
        else:
            # Si no se encuentra nada, informamos al usuario.
            print(f"✅ No se encontraron URLs que terminen en {', '.join(sufijos)} en '{archivo_entrada}'.")
            # Creamos el archivo de salida vacío por si acaso.
            if not os.path.exists(archivo_salida):
                 with open(archivo_salida, 'w', encoding='utf-8') as f:
                     pass

    except FileNotFoundError:
        print(f"❌ Error: El archivo de entrada '{archivo_entrada}' no fue encontrado. Asegúrate de que exista.")
    except Exception as e:
        print(f"❌ Ocurrió un error: {e}")

# Ejecutar la función
extraer_urls_duplicadas(archivo_entrada, archivo_salida, sufijos_duplicados)