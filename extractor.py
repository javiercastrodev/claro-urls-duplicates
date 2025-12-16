import re

# Nombre del archivo de entrada y salida
archivo_entrada = "urls-sitemaps.txt"
archivo_salida = "claro_urls.txt"

def extraer_urls_y_guardar(archivo_entrada, archivo_salida):
    """
    Lee un archivo de texto, extrae URLs y las guarda en un nuevo archivo.
    """
    try:
        # 1. Leer el contenido del archivo de entrada
        with open(archivo_entrada, 'r', encoding='utf-8') as f:
            contenido = f.read()

        # 2. Usar una expresión regular para encontrar URLs
        # El patrón busca cadenas que empiezan con 'http' o 'https', 
        # seguidas de caracteres que no sean espacios, hasta encontrar un espacio.
        # Esto es simple y funciona bien para el formato de tu texto.
        patron_url = r'https?://[^\s]+'
        
        urls_encontradas = re.findall(patron_url, contenido)

        # 3. Filtrar solo URLs únicas (opcional, pero buena práctica)
        urls_unicas = sorted(list(set(urls_encontradas)))

        # 4. Escribir las URLs encontradas en el archivo de salida
        with open(archivo_salida, 'w', encoding='utf-8') as f:
            # Escribir cada URL en una nueva línea
            f.write('\n'.join(urls_unicas))

        print(f"✅ Se han extraído {len(urls_unicas)} URLs y se han guardado en '{archivo_salida}'.")

    except FileNotFoundError:
        print(f"❌ Error: El archivo de entrada '{archivo_entrada}' no fue encontrado.")
    except Exception as e:
        print(f"❌ Ocurrió un error: {e}")

# Ejecutar la función
extraer_urls_y_guardar(archivo_entrada, archivo_salida)