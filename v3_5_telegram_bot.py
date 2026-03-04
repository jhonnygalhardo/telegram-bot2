import requests
import asyncio
import json
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# =========================
# CONFIGURAÇÕES
# =========================
TELEGRAM_TOKEN = "SEU_TELEGRAM_TOKEN"
CHAT_ID = "SEU_CHAT_ID"
API_KEY = "SUA_API_KEY_BZZOIRO"
BASE_URL = "https://sports.bzzoiro.com/api/v1"

MIN_PROB_VITORIA = 60     # % mínima para alertas
MIN_CONFIANCA = 80        # % mínima de confiança
CHANGE_THRESHOLD = 5      # % de mudança significativa para alertas
CHECK_INTERVAL = 5*60     # 5 minutos

ALERTS_FILE = "alerted_matches.json"

# =========================
# ARMAZENAR ALERTAS ENVIADOS
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
        partidas = [(str(m["id"]), f"{m['home_team']['name']} x {m['away_team']['name']}") for m in data["matches"]]
        return partidas
    except requests.RequestException as e:
        print(f"Erro ao obter jogos do dia: {e}")
        return []

# =========================
# OBTER PREVISÃO DE PARTIDA
# =========================
def previsao_partida(match_id):
    headers = {"Authorization": f"Token {API_KEY}", "Accept": "application/json"}
    try:
        resp = requests.get(f"{BASE_URL}/predictions/matches/{match_id}", headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()["predictions"]
    except:
        return None

# =========================
# FORMATAR MENSAGEM
# =========================
def formatar_mensagem(nome_jogo, p, match_id=None):
    odds_casa = round(100 / (p['home_win_prob']*100), 2)
    odds_empate = round(100 / (p['draw_prob']*100), 2)
    odds_fora = round(100 / (p['away_win_prob']*100), 2)
    texto = (
        f"⚽️ Previsão da Partida: {nome_jogo}\n"
        f"🆔 ID da Partida: {match_id}\n\n"
        f"🏆 Vitória Casa: {p['home_win_prob']*100:.1f}% (Odds: {odds_casa})\n"
        f"🤝 Empate: {p['draw_prob']*100:.1f}% (Odds: {odds_empate})\n"
        f"🏆 Vitória Fora: {p['away_win_prob']*100:.1f}% (Odds: {odds_fora})\n"
        f"🔎 Nível de Confiança: {p['confidence_score']*100:.1f}%"
    )
    return texto

# =========================
# ENVIAR ALERTAS EM TEMPO REAL
# =========================
async def enviar_alertas(app):
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
                texto = formatar_mensagem(nome_jogo, p, match_id)
                await app.bot.send_message(chat_id=CHAT_ID, text=texto)
                alertas[key] = {"prob": max_prob, "conf": conf}
                await asyncio.sleep(1)

            # Armazena para ranking
            melhores_jogos.append((max_prob, conf, nome_jogo, p))

    salvar_alertas(alertas)

    # Ranking top 5 atualizado
    if melhores_jogos:
        melhores_jogos.sort(reverse=True, key=lambda x: (x[0], x[1]))
        top5 = melhores_jogos[:5]
        ranking_msg = "🏅 Top 5 Jogos Mais Confiáveis do Dia:\n\n"
        for i, (prob, conf, nome_jogo, _) in enumerate(top5, 1):
            ranking_msg += f"{i}. {nome_jogo} | Prob: {prob:.1f}% | Conf: {conf:.1f}%\n"
        await app.bot.send_message(chat_id=CHAT_ID, text=ranking_msg)

# =========================
# CONSULTAS SOB DEMANDA PELO NOME DO TIME
# =========================
async def consulta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.strip().lower()
    partidas = jogos_do_dia()

    partida_encontrada = None
    for id, nome in partidas:
        if all(time in nome.lower() for time in msg.split()):
            partida_encontrada = (id, nome)
            break

    if not partida_encontrada:
        await update.message.reply_text("Não encontrei a partida. Digite pelo menos um time do jogo.")
        return

    match_id, nome_jogo = partida_encontrada
    p = previsao_partida(match_id)
    if not p:
        await update.message.reply_text("Não foi possível obter a previsão.")
        return

    texto = formatar_mensagem(nome_jogo, p, match_id)
    await update.message.reply_text(texto)

# =========================
# MAIN - BOT TELEGRAM
# =========================
async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), consulta))

    # Rodar alerta automático em loop paralelo
    async def loop_alertas():
        while True:
            try:
                await enviar_alertas(app)
                await asyncio.sleep(CHECK_INTERVAL)
            except Exception as e:
                print(f"Erro no loop: {e}")
                await asyncio.sleep(60)

    asyncio.create_task(loop_alertas())
    print("Bot iniciado e rodando em tempo real...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
