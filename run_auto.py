from playwright.sync_api import sync_playwright
import chompjs
import time
import re
import os
import random
import argparse
import requests
from dotenv import load_dotenv
from datetime import datetime


# Carga el archivo .env cuando se ejecuta localmente.
# En GitHub Actions se utilizarán GitHub Secrets.
load_dotenv()


# ==========================================
# CONFIGURACIÓN DE TELEGRAM
# ==========================================

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def enviar_telegram(mensaje):
    """
    Envía un mensaje al chat de Telegram configurado.
    """

    if not TOKEN:
        print("[-] No se ha configurado TELEGRAM_TOKEN.")
        return False

    if not CHAT_ID:
        print("[-] No se ha configurado TELEGRAM_CHAT_ID.")
        return False

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": mensaje,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=15,
        )

        response.raise_for_status()

        resultado = response.json()

        if resultado.get("ok"):
            print("[+] Notificación enviada correctamente a Telegram.")
            return True

        print(
            "[-] Telegram respondió, pero no confirmó "
            "el envío del mensaje."
        )
        print(resultado)

    except requests.RequestException as error:
        print(f"[-] Error enviando el mensaje a Telegram: {error}")

    except ValueError as error:
        print(f"[-] Telegram devolvió una respuesta no válida: {error}")

    return False


# ==========================================
# PROCESAMIENTO DE LA RESPUESTA DWR
# ==========================================

def parse_dwr_response(raw_text):
    """
    Extrae el objeto JavaScript contenido en la respuesta DWR
    y lo transforma en un objeto de Python.
    """

    try:
        match = re.search(
            r'handleCallback\(".*?",".*?",(.*?)\);?\s*\}\)\(\);',
            raw_text,
            re.DOTALL,
        )

        if not match:
            print(
                "[-] No se encontró el objeto esperado "
                "en la respuesta DWR."
            )
            return None

        return chompjs.parse_js_object(match.group(1))

    except Exception as error:
        print(f"[-] No se pudo procesar la respuesta DWR: {error}")
        return None


# ==========================================
# SELECCIÓN DE FECHA
# ==========================================

def hacer_clic_en_fecha(page, fecha_str):
    """
    Abre el calendario de Renfe y selecciona una fecha
    con formato DD/MM/AAAA.
    """

    try:
        fecha_objetivo = datetime.strptime(
            fecha_str,
            "%d/%m/%Y",
        )
    except ValueError:
        raise ValueError(
            "La fecha debe tener formato DD/MM/AAAA. "
            f"Valor recibido: {fecha_str}"
        )

    fecha_actual = datetime.now()

    meses_diferencia = (
        (fecha_objetivo.year - fecha_actual.year) * 12
        + fecha_objetivo.month
        - fecha_actual.month
    )

    if meses_diferencia < 0:
        raise ValueError(
            "La fecha indicada pertenece a un mes anterior "
            "al mes actual."
        )

    # Abre el selector de fechas.
    page.locator("#first-input").click()
    page.locator("label[for='trip-go']").click()

    # Avanza hasta el mes solicitado.
    for _ in range(meses_diferencia):
        page.locator(".lightpick__next-action").click()
        page.wait_for_timeout(150)

    dia = fecha_objetivo.day

    selector_dia = (
        "//div["
        "contains(@class, 'lightpick__day') "
        "and not(contains(@class, 'is-next-month')) "
        "and not(contains(@class, 'is-previous-month')) "
        f"and normalize-space(text())='{dia}'"
        "]"
    )

    dia_calendario = page.locator(selector_dia).first

    dia_calendario.wait_for(
        state="visible",
        timeout=10000,
    )

    dia_calendario.click()

    boton_aplicar = page.locator(
        ".lightpick__apply-action-sub"
    )

    if boton_aplicar.count() > 0:
        try:
            boton_aplicar.click(
                delay=100,
                timeout=5000,
            )
        except Exception:
            # Algunos cambios de la web pueden hacer que la fecha
            # quede aplicada sin necesidad de pulsar este botón.
            pass


# ==========================================
# AUTOMATIZACIÓN DEL NAVEGADOR
# ==========================================

def buscar_y_capturar_datos(origen, destino, fecha):
    """
    Abre Renfe, realiza una búsqueda y captura la respuesta
    de la petición que contiene el listado de trenes.
    """

    datos_extraidos = None

    def interceptar_respuesta(response):
        nonlocal datos_extraidos

        if (
            "trainEnlacesManager.getTrainsList.dwr" in response.url
            and response.request.method == "POST"
        ):
            try:
                raw_text = response.text()
                datos_parseados = parse_dwr_response(raw_text)

                if datos_parseados:
                    datos_extraidos = datos_parseados
                    print("[+] Respuesta de trenes capturada.")

            except Exception as error:
                print(
                    "[-] Error leyendo la respuesta "
                    f"de Renfe: {error}"
                )

    with sync_playwright() as playwright:
        browser = None

        try:
            browser = playwright.chromium.launch(
                headless=True,
                args=[
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )

            context = browser.new_context(
                viewport={
                    "width": 1920,
                    "height": 1080,
                },
                locale="es-ES",
            )

            page = context.new_page()

            page.set_default_timeout(20000)
            page.set_default_navigation_timeout(60000)

            # Escucha todas las respuestas de red.
            page.on("response", interceptar_respuesta)

            print("[*] Accediendo a la página de Renfe...")

            page.goto(
                "https://www.renfe.com/es/es",
                wait_until="domcontentloaded",
                timeout=60000,
            )

            # Aceptar cookies si aparece el aviso.
            boton_cookies = page.locator(
                "#onetrust-accept-btn-handler"
            )

            try:
                boton_cookies.wait_for(
                    state="visible",
                    timeout=8000,
                )
                boton_cookies.click()
                print("[+] Cookies aceptadas.")

            except Exception:
                print(
                    "[*] El aviso de cookies no apareció "
                    "o ya estaba aceptado."
                )

            # Introducir estación de origen.
            print(f"[*] Seleccionando origen: {origen}")

            campo_origen = page.locator("#origin")
            campo_origen.wait_for(
                state="visible",
                timeout=20000,
            )
            campo_origen.fill("")
            campo_origen.type(
                origen,
                delay=100,
            )

            opcion_origen = page.locator(
                "#awesomplete_list_1_item_0"
            )

            opcion_origen.wait_for(
                state="visible",
                timeout=15000,
            )
            opcion_origen.click()

            # Introducir estación de destino.
            print(f"[*] Seleccionando destino: {destino}")

            campo_destino = page.locator("#destination")
            campo_destino.fill("")
            campo_destino.type(
                destino,
                delay=100,
            )

            opcion_destino = page.locator(
                "#awesomplete_list_2_item_0"
            )

            opcion_destino.wait_for(
                state="visible",
                timeout=15000,
            )
            opcion_destino.click()

            # Seleccionar fecha.
            print(f"[*] Seleccionando fecha: {fecha}")
            hacer_clic_en_fecha(page, fecha)

            # Ejecutar búsqueda.
            print("[*] Pulsando el botón de búsqueda...")

            boton_buscar = page.locator("#ticketSearchBt")

            boton_buscar.wait_for(
                state="visible",
                timeout=15000,
            )

            boton_buscar.click()

            # Espera a que la petición de trenes sea interceptada.
            tiempo_limite = time.monotonic() + 30

            while (
                datos_extraidos is None
                and time.monotonic() < tiempo_limite
            ):
                page.wait_for_timeout(500)

            if datos_extraidos is None:
                print(
                    "[-] No se capturó la respuesta de trenes "
                    "dentro del tiempo establecido."
                )

        except Exception as error:
            print(
                "[-] Error durante la navegación automatizada: "
                f"{error}"
            )

        finally:
            if browser is not None:
                browser.close()

    return datos_extraidos


# ==========================================
# FUNCIONES AUXILIARES
# ==========================================

def convertir_hora_a_minutos(hora):
    """
    Convierte una hora HH:MM a minutos desde medianoche.
    Por ejemplo, 08:30 se convierte en 510.
    """

    try:
        hora_objeto = datetime.strptime(
            hora,
            "%H:%M",
        )

        return hora_objeto.hour * 60 + hora_objeto.minute

    except (ValueError, TypeError):
        return None


def validar_argumentos(args):
    """
    Comprueba que los argumentos recibidos sean válidos.
    """

    try:
        fecha = datetime.strptime(
            args.fecha,
            "%d/%m/%Y",
        )
    except ValueError:
        raise ValueError(
            "La fecha debe tener formato DD/MM/AAAA."
        )

    hoy = datetime.now().date()

    if fecha.date() < hoy:
        raise ValueError(
            "La fecha de viaje no puede estar en el pasado."
        )

    salida_minutos = convertir_hora_a_minutos(args.salida)
    llegada_minutos = convertir_hora_a_minutos(args.llegada)

    if salida_minutos is None:
        raise ValueError(
            "La hora de salida debe tener formato HH:MM."
        )

    if llegada_minutos is None:
        raise ValueError(
            "La hora de llegada debe tener formato HH:MM."
        )

    if args.duracion <= 0:
        raise ValueError(
            "La duración máxima debe ser mayor que cero."
        )

    if args.intervalo_minimo <= 0:
        raise ValueError(
            "El intervalo mínimo debe ser mayor que cero."
        )

    if args.intervalo_maximo < args.intervalo_minimo:
        raise ValueError(
            "El intervalo máximo no puede ser menor "
            "que el intervalo mínimo."
        )

    if args.max_minutos <= 0:
        raise ValueError(
            "El tiempo máximo de ejecución debe ser "
            "mayor que cero."
        )


def analizar_trenes(data, args):
    """
    Filtra los trenes utilizando los argumentos indicados,
    envía los avisos de Telegram y devuelve el número
    de billetes encontrados.
    """

    if not data:
        print("[-] Renfe no devolvió datos.")
        return 0

    listado_trenes = data.get("listadoTrenes")

    if not listado_trenes:
        print(
            "[-] La respuesta no contiene un listado "
            "de trenes válido."
        )
        return 0

    primer_listado = listado_trenes[0]

    trenes = primer_listado.get(
        "listviajeViewEnlaceBean",
        [],
    )

    if not trenes:
        print("[-] No aparecen trenes en la respuesta.")
        return 0

    print(f"[+] Escaneando {len(trenes)} trenes...")

    salida_minima = convertir_hora_a_minutos(
        args.salida
    )

    llegada_maxima = convertir_hora_a_minutos(
        args.llegada
    )

    encontrados = 0

    for tren in trenes:
        h_salida = str(
            tren.get("horaSalida", "00:00")
        )

        h_llegada = str(
            tren.get("horaLlegada", "23:59")
        )

        salida_tren = convertir_hora_a_minutos(
            h_salida
        )

        llegada_tren = convertir_hora_a_minutos(
            h_llegada
        )

        if salida_tren is None or llegada_tren is None:
            continue

        try:
            duracion_min = int(
                tren.get(
                    "duracionViajeTotalEnMinutos",
                    0,
                )
            )
        except (TypeError, ValueError):
            duracion_min = 0

        tarifas = tren.get("tarifasDisponibles")

        solo_h = (
            str(
                tren.get(
                    "soloPlazaH",
                    "false",
                )
            ).lower()
            == "true"
        )

        cumple_horario = (
            salida_tren >= salida_minima
            and llegada_tren <= llegada_maxima
        )

        cumple_duracion = (
            duracion_min <= args.duracion
        )

        tiene_tarifas = (
            tarifas is not None
            and tarifas != "null"
            and tarifas != []
            and tarifas != {}
            and tarifas != ""
        )

        if (
            cumple_horario
            and cumple_duracion
            and tiene_tarifas
            and not solo_h
        ):
            encontrados += 1

            tipo = tren.get(
                "tipoTrenUno",
                "Tren",
            )

            precio = tren.get(
                "tarifaMinima",
                "No disponible",
            )

            mensaje = (
                "<b>¡BILLETE ENCONTRADO!</b> 🚄\n\n"
                f"<b>Origen:</b> {args.origen}\n"
                f"<b>Destino:</b> {args.destino}\n"
                f"<b>Fecha:</b> {args.fecha}\n"
                f"<b>Tipo:</b> {tipo}\n"
                f"<b>Salida:</b> {h_salida}\n"
                f"<b>Llegada:</b> {h_llegada}\n"
                f"<b>Duración:</b> {duracion_min} min\n"
                f"<b>Precio:</b> {precio} €\n\n"
                "¡Corre a la web de Renfe!"
            )

            print(
                "✅ Plaza encontrada: "
                f"{h_salida} -> {h_llegada} "
                f"({precio} €)"
            )

            enviar_telegram(mensaje)

            # Evita enviar demasiados mensajes seguidos
            # si hay varios trenes compatibles.
            time.sleep(2)

    if encontrados == 0:
        print(
            "[-] No se encontraron plazas que "
            "cumplan los filtros."
        )

    return encontrados


# ==========================================
# PROGRAMA PRINCIPAL
# ==========================================

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Monitor de disponibilidad de billetes de Renfe"
        )
    )

    parser.add_argument(
        "-o",
        "--origen",
        type=str,
        required=True,
        help="Estación de origen",
    )

    parser.add_argument(
        "-d",
        "--destino",
        type=str,
        required=True,
        help="Estación de destino",
    )

    parser.add_argument(
        "-f",
        "--fecha",
        type=str,
        required=True,
        help="Fecha de viaje con formato DD/MM/AAAA",
    )

    parser.add_argument(
        "-s",
        "--salida",
        type=str,
        default="00:00",
        help="Hora mínima de salida, formato HH:MM",
    )

    parser.add_argument(
        "-l",
        "--llegada",
        type=str,
        default="23:59",
        help="Hora máxima de llegada, formato HH:MM",
    )

    parser.add_argument(
        "-t",
        "--duracion",
        type=int,
        default=999,
        help="Duración máxima del viaje en minutos",
    )

    parser.add_argument(
        "--intervalo-minimo",
        type=int,
        default=8,
        help=(
            "Espera mínima entre consultas, en minutos"
        ),
    )

    parser.add_argument(
        "--intervalo-maximo",
        type=int,
        default=12,
        help=(
            "Espera máxima entre consultas, en minutos"
        ),
    )

    parser.add_argument(
        "--max-minutos",
        type=int,
        default=165,
        help=(
            "Tiempo máximo total de monitorización "
            "en minutos"
        ),
    )

    args = parser.parse_args()

    try:
        validar_argumentos(args)
    except ValueError as error:
        parser.error(str(error))

    print()
    print("=========================================")
    print("🚄 RENFE BOT TICKET AVAILABILITY")
    print("=========================================")
    print()
    print(f"Origen:                {args.origen}")
    print(f"Destino:               {args.destino}")
    print(f"Fecha:                 {args.fecha}")
    print(f"Salida mínima:         {args.salida}")
    print(f"Llegada máxima:        {args.llegada}")
    print(f"Duración máxima:       {args.duracion} min")
    print(
        "Intervalo:             "
        f"{args.intervalo_minimo}-"
        f"{args.intervalo_maximo} min"
    )
    print(
        f"Tiempo máximo:         {args.max_minutos} min"
    )
    print()

    inicio = time.monotonic()
    numero_ciclo = 0
    billetes_encontrados = False

    try:
        while not billetes_encontrados:
            tiempo_transcurrido = (
                time.monotonic() - inicio
            ) / 60

            tiempo_restante = (
                args.max_minutos - tiempo_transcurrido
            )

            if tiempo_restante <= 0:
                print(
                    "[*] Se ha alcanzado el tiempo máximo "
                    "de monitorización."
                )
                break

            numero_ciclo += 1

            print()
            print("-----------------------------------------")
            print(
                f"[*] Ciclo número {numero_ciclo}"
            )
            print(
                f"[*] Hora: {time.strftime('%H:%M:%S')}"
            )
            print(
                "[*] Tiempo restante aproximado: "
                f"{tiempo_restante:.1f} minutos"
            )
            print("-----------------------------------------")

            data = buscar_y_capturar_datos(
                args.origen,
                args.destino,
                args.fecha,
            )

            encontrados = analizar_trenes(
                data,
                args,
            )

            if encontrados > 0:
                billetes_encontrados = True

                print()
                print(
                    f"[+] Se encontraron {encontrados} "
                    "billete(s) compatible(s)."
                )
                print(
                    "[+] Las notificaciones han sido "
                    "procesadas."
                )
                print("[*] Finalizando el monitor.")
                break

            # Vuelve a calcular el tiempo restante después
            # de completar la búsqueda.
            tiempo_transcurrido = (
                time.monotonic() - inicio
            ) / 60

            tiempo_restante = (
                args.max_minutos - tiempo_transcurrido
            )

            if tiempo_restante <= 0:
                print(
                    "[*] Se ha alcanzado el tiempo máximo "
                    "de monitorización."
                )
                break

            minutos_espera = random.randint(
                args.intervalo_minimo,
                args.intervalo_maximo,
            )

            # No espera más tiempo del que queda disponible.
            minutos_espera = min(
                minutos_espera,
                max(0, int(tiempo_restante)),
            )

            if minutos_espera <= 0:
                print(
                    "[*] No queda suficiente tiempo para "
                    "iniciar otro ciclo."
                )
                break

            print(
                f"[*] Próxima comprobación dentro de "
                f"{minutos_espera} minutos."
            )

            time.sleep(minutos_espera * 60)

    except KeyboardInterrupt:
        print()
        print("[*] Monitor detenido manualmente.")

    except Exception as error:
        print()
        print(f"[-] Error no controlado: {error}")
        raise

    finally:
        duracion_total = (
            time.monotonic() - inicio
        ) / 60

        print()
        print(
            "[*] Tiempo total de ejecución: "
            f"{duracion_total:.1f} minutos."
        )
        print("[*] Ejecución finalizada.")


if __name__ == "__main__":
    main()