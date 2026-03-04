import requests
import json
import os
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters
)

# =========================
# CONFIGURAÇÕES
# =========================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_KEY = os.getenv("API_KEY_BZZOIRO")
BASE_URL = "https://sports.bzzoiro.com/api/v1"

MIN_PROB_VITORIA = 60     # % mínima para alertas
MIN_CONFIANCA = 80        # % mínima de confiança
CHANGE_THRESHOLD = 5      # % de mudança significativa para alertas
CHECK_INTERVAL = 5*60     # 5 minutos

ALERTS_FILE = "alerted_matches.json"

# =========================
# ARMAZENAR ALERTAS
# =========================
def carregar_alertas():
    if os.path.exists(ALERTS_FILE):
        with open(ALERTS_FILE, "r") as f:
            return json.load(f)
    return {}

def salvar_alertas(alerts):
    with open(ALERTS_FILE, "w") as f:
        json.dump(alerts, f)

# =========================
# OBTER JOGOS DO DIA
# =========================
def jogos_do_dia():
    headers = {"Authorization": f"Token {API_KEY}", "Accept": "application/json"}
    try:
        resp = requests.get(f"{BASE_URL}/matches/today", headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # Retorna lista: (id, "TimeA x TimeB")
        partidas = [(m["id"], f"{m['home_team']['name']} x {m['away_team']['name']}") for m in data.get("matches",[])]
        return partidas
    except requests.RequestException as e:
        print(f"Erro ao obter jogos do dia: {e}")
        return []

# =========================
# ENCONTRAR JOGO POR NOME
# =========================
def buscar_jogo_por_nome(nome_jogo):
    partidas = jogos_do_dia()
    nome_jogo_lower = nome_jogo.lower()
    for match_id, nome in partidas:
        if all(t.lower() in nome_jogo_lower for t in nome_jogo_lower.split()):
            return match_id, nome
    return None, None

# =========================
# OBTER PREVISÃO DE PARTIDA
# =========================
def previsao_partida(match_id):
    headers = {"Authorization": f"Token {API_KEY}", "Accept": "application/json"}
    try:
        resp = requests.get(f"{BASE_URL}/predictions/matches/{match_id}", headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json().get("predictions")
    except:
        return None

# =========================
# FORMATAR MENSAGEM
# =========================
def formatar_mensagem(nome_jogo, p):
    odds_casa = round(100 / (p['home_win_prob']*100), 2)
    odds_empate = round(100 / (p['draw_prob']*100), 2)
    odds_fora = round(100 / (p['away_win_prob']*100), 2)
    texto = (
        f"⚽️ Previsão da Partida: {nome_jogo}\n\n"
        f"🏆 Vitória Casa: {p['home_win_prob']*100:.1f}% (Odds: {odds_casa})\n"
        f"🤝 Empate: {p['draw_prob']*100:.1f}% (Odds: {odds_empate})\n"
        f"🏆 Vitória Fora: {p['away_win_prob']*100:.1f}% (Odds: {odds_fora})\n"
        f"🔎 Nível de Confiança: {p['confidence_score']*100:.1f}%"
    )
    return texto

# =========================
# CONSULTA SOB DEMANDA
# =========================
async def consulta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.strip()
    match_id, nome_jogo = buscar_jogo_por_nome(msg)
    if not match_id:
        await update.message.reply_text("❌ Jogo não encontrado. Use o formato: Palmeiras x Novorizontino")
        return
    p = previsao_partida(match_id)
    if not p:
        await update.message.reply_text("❌ Não foi possível obter a previsão.")
        return
    texto = formatar_mensagem(nome_jogo, p)
    await update.message.reply_text(texto)

# =========================
# ALERTAS AUTOMÁTICOS
# =========================
async def enviar_alertas(bot_app):
    alertas = carregar_alertas()
    partidas = jogos_do_dia()
    melhores_jogos = []

    for match_id, nome_jogo in partidas:
        p = previsao_partida(match_id)
        if not p:
            continue

        max_prob = max(p['home_win_prob']*100, p['away_win_prob']*100)
        conf = p['confidence_score']*100

        if max_prob >= MIN_PROB_VITORIA and conf >= MIN_CONFIANCA:
            key = str(match_id)
            last_sent = alertas.get(key, {})
            changed = (not last_sent or abs(last_sent.get("prob",0)-max_prob) >= CHANGE_THRESHOLD or abs(last_sent.get("conf",0)-conf) >= CHANGE_THRESHOLD)

            if changed:
                texto = formatar_mensagem(nome_jogo, p)
                await bot_app.bot.send_message(chat_id=CHAT_ID, text=texto)
                alertas[key] = {"prob": max_prob, "conf": conf}

            # Armazena para ranking
            melhores_jogos.append((max_prob, conf, nome_jogo, p))

    salvar_alertas(alertas)

    # Ranking top 5
    if melhores_jogos:
        melhores_jogos.sort(reverse=True, key=lambda x: (x[0], x[1]))
        top5 = melhores_jogos[:5]
        ranking_msg = "🏅 Top 5 Jogos Mais Confiáveis do Dia:\n\n"
        for i, (prob, conf, nome_jogo, _) in enumerate(top5, 1):
            ranking_msg += f"{i}. {nome_jogo} | Prob: {prob:.1f}% | Conf: {conf:.1f}%\n"
        await bot_app.bot.send_message(chat_id=CHAT_ID, text=ranking_msg)

# =========================
# MAIN ASYNC
# =========================
async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, consulta))

    print("✅ Bot iniciado e ouvindo mensagens...")

    # Loop de alertas em background
    async def alert_loop():
        while True:
            try:
                await enviar_alertas(app)
            except Exception as e:
                print("Erro no loop de alertas:", e)
            await asyncio.sleep(CHECK_INTERVAL)

    asyncio.create_task(alert_loop())

    await app.run_polling()

# =========================
# START
# =========================
if __name__ == "__main__":
    asyncio.run(main())
