"""
Servidor Ariston NET para atalhos do iPhone (Siri)
==================================================
Ficheiro unico. Credenciais e API key vem SEMPRE de variaveis de ambiente
(painel do Render: Environment). Nunca escrever palavras-passe no codigo.

Variaveis de ambiente:
    ARISTON_USERNAME   email da conta Ariston NET (obrigatoria)
    ARISTON_PASSWORD   palavra-passe da conta (obrigatoria)
    API_KEY            chave que os atalhos enviam (obrigatoria)
    ARISTON_GW         id do gateway (opcional)

Os atalhos enviam a chave no cabecalho  X-API-Key  (ou ?api_key=...).
"""

import os
import time
import hmac
import json
import logging
import threading

from flask import Flask, Response, request

ARISTON_USERNAME = os.environ.get("ARISTON_USERNAME", "")
ARISTON_PASSWORD = os.environ.get("ARISTON_PASSWORD", "")
ARISTON_GW = os.environ.get("ARISTON_GW", "")
API_KEY = os.environ.get("API_KEY", "")

RETRY_SECONDS = 30      # intervalo minimo entre tentativas de ligacao
WAIT_FOR_DATA = 20      # segundos a esperar pela primeira leitura
TEMP_MIN, TEMP_MAX, TEMP_STEP = 40, 80, 5

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("ariston")

app = Flask(__name__)

api = None
last_error = None
_last_attempt = 0.0
_init_lock = threading.Lock()
_api_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Ligacao ao Ariston NET (com nova tentativa automatica)
# ---------------------------------------------------------------------------
def _has_data():
    try:
        return api is not None and bool(api.sensor_values)
    except Exception:
        return False


def connect():
    """Liga ao Ariston NET. Se falhar, tenta de novo passados RETRY_SECONDS."""
    global api, last_error, _last_attempt
    with _init_lock:
        if _has_data():
            return True
        if time.time() - _last_attempt < RETRY_SECONDS:
            return False
        _last_attempt = time.time()

        if not ARISTON_USERNAME or not ARISTON_PASSWORD:
            last_error = "Credenciais nao configuradas"
            log.error(last_error)
            return False
        try:
            if api is None:
                from aristonremotethermo.ariston import AristonHandler
                log.info("A ligar ao Ariston NET...")
                handler = AristonHandler(
                    username=ARISTON_USERNAME,
                    password=ARISTON_PASSWORD,
                    logging_level="WARNING",
                    gw=ARISTON_GW,
                )
                handler.start()
                api = handler
            for _ in range(WAIT_FOR_DATA):
                if _has_data():
                    break
                time.sleep(1)
            if _has_data():
                last_error = None
                log.info("Ligado ao Ariston NET.")
                return True
            last_error = "Sem dados do Ariston NET (login falhou ou sem resposta)"
            log.warning(last_error)
            return False
        except Exception as e:
            last_error = repr(e)
            log.exception("Erro ao ligar ao Ariston NET")
            return False


def get_sensor(name):
    if not _has_data() and not connect():
        return None
    try:
        item = api.sensor_values.get(name)
        return item.get("value") if item else None
    except Exception as e:
        log.error("Erro ao ler sensor %s: %s", name, e)
        return None


def set_first(options):
    """Tenta cada conjunto de valores ate um funcionar. Devolve (ok, erro)."""
    if not _has_data() and not connect():
        return False, "Sem ligacao ao Ariston NET"
    err = None
    for kwargs in options:
        try:
            with _api_lock:
                api.set_http_data(**kwargs)
            return True, None
        except Exception as e:
            err = str(e)
            log.warning("Falhou %s: %s", kwargs, e)
    return False, err


# ---------------------------------------------------------------------------
# Respostas e autenticacao
# ---------------------------------------------------------------------------
def text(body, status=200):
    return Response(body, status=status, mimetype="text/plain; charset=utf-8")


def js(data, status=200):
    return Response(json.dumps(data, ensure_ascii=False, default=str), status=status,
                    mimetype="application/json; charset=utf-8")


def authorized():
    if not API_KEY:
        return False  # sem chave configurada, nada funciona (falha segura)
    given = request.headers.get("X-API-Key") or request.args.get("api_key", "")
    return hmac.compare_digest(given.encode(), API_KEY.encode())


def protected(fn):
    def wrapper(*args, **kwargs):
        if not API_KEY:
            return text("Servidor sem API_KEY configurada.", 503)
        if not authorized():
            return text("Acesso negado.", 401)
        return fn(*args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper


def act(options, ok_message):
    ok, err = set_first(options)
    return text(ok_message) if ok else text(f"Erro: {err}", 500)


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------
@app.route("/health")
def health():
    # Publica e sem detalhes: serve para acordar o servidor e para o ping.
    if not _has_data():
        threading.Thread(target=connect, daemon=True).start()
    return js({"status": "ok", "connected": _has_data()})


@app.route("/")
def index():
    return text("Servidor Ariston NET - OK")


@app.route("/diag")
@protected
def diag():
    return js({"connected": _has_data(), "last_error": last_error,
               "sensors": len(api.sensor_values) if _has_data() else 0})


@app.route("/raw")
@protected
def raw():
    """Mostra todos os sensores e valores. Util para descobrir os valores
    de dhw_mode do teu modelo."""
    if not _has_data() and not connect():
        return js({"error": last_error or "sem ligacao"}, 503)
    return js(api.sensor_values)


@app.route("/temp")
@protected
def temp():
    t = get_sensor("dhw_storage_temperature")
    return text(str(t)) if t is not None else text("N/A", 503)


@app.route("/target")
@protected
def target():
    t = get_sensor("dhw_set_temperature")
    return text(str(t)) if t is not None else text("N/A", 503)


@app.route("/status")
@protected
def status():
    t = get_sensor("dhw_storage_temperature")
    tgt = get_sensor("dhw_set_temperature")
    mode = get_sensor("dhw_mode")
    eco = get_sensor("dhw_comfort_function")
    mode_map = {0: "Desligado", 1: "Manual", 5: "Programado", 9: "Boost"}
    if t is None and tgt is None:
        return text("Sem dados do termoacumulador.", 503)
    return text("\n".join([
        f"Temperatura atual: {t} graus",
        f"Temperatura alvo: {tgt} graus",
        f"Modo: {mode_map.get(mode, mode)}",
        f"ECO: {'Sim' if eco else 'Nao'}",
    ]))


@app.route("/boost")
@app.route("/mode/boost")
@protected
def boost():
    return act([{"dhw_mode": 9}, {"dhw_mode": "BOOST"}],
               "Boost ativado. O termoacumulador vai aquecer ao maximo.")


@app.route("/eco/on")
@protected
def eco_on():
    return act([{"dhw_comfort_function": True}, {"dhw_mode": "ECO"}], "Modo ECO ativado.")


@app.route("/eco/off")
@protected
def eco_off():
    return act([{"dhw_comfort_function": False}], "Modo ECO desativado.")


@app.route("/power/on")
@app.route("/mode/manual")
@protected
def power_on():
    return act([{"dhw_mode": 1}], "Termoacumulador ligado em modo manual.")


@app.route("/power/off")
@protected
def power_off():
    return act([{"dhw_mode": "OFF"}, {"dhw_mode": 0}], "Termoacumulador desligado.")


@app.route("/mode/program")
@protected
def mode_program():
    return act([{"dhw_mode": 5}], "Modo programado ativado.")


def _change_target(delta):
    t = get_sensor("dhw_set_temperature")
    if t is None:
        return text("Nao foi possivel ler a temperatura alvo.", 503)
    new = max(TEMP_MIN, min(TEMP_MAX, int(round(float(t))) + delta))
    ok, err = set_first([{"dhw_set_temperature": new}])
    return text(f"Temperatura alvo: {new} graus.") if ok else text(f"Erro: {err}", 500)


@app.route("/temp/up")
@protected
def temp_up():
    return _change_target(+TEMP_STEP)


@app.route("/temp/down")
@protected
def temp_down():
    return _change_target(-TEMP_STEP)


@app.route("/temp/set/<int:valor>")
@protected
def temp_set(valor):
    if not TEMP_MIN <= valor <= TEMP_MAX:
        return text(f"A temperatura deve estar entre {TEMP_MIN} e {TEMP_MAX} graus.", 400)
    return act([{"dhw_set_temperature": valor}], f"Temperatura alvo definida para {valor} graus.")


# Arranque em segundo plano (com --workers 1 so existe uma sessao Ariston)
threading.Thread(target=connect, daemon=True).start()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=False, threaded=True)
