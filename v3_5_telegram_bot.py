import asyncio
import requests
import json
import os
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
API_KEY = os.environ.get("API_KEY")

ALERTS_FILE = "alerted_matches.json"

bot = Bot(token=TELEGRAM_TOKEN)

def carregar_alertas():
    if os.path.exists(ALERTS_FILE):
        with open(ALERTS_FILE, "r") as f:
            return json.load(f)
    return {}

def salvar_alertas(alerts):
    with open(ALERTS_FILE, "w") as f:
        json.dump(alerts, f)

def jogos_do_dia():
    headers = {"Authorization": f"Token {API_KEY}", "Accept": "application/json"}
    try:
        resp = requests.get("https://sports.bzzoiro.com/api/v1/matches/today", headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        partidas = [(m["id"], f"{m['home_team']['name']} x {m['away_team']['name']}") for m in data["matches"]]
        return partidas
    except Exception as e:
        print(f"Erro: {e}")
        return []

def encontrar_jogo_por_nome(texto):
    texto = texto.lower().strip()
    partidas = jogos_do_dia()
    for match_id, nome_jogo in partidas:
        if all(time.lower() in nome_jogo.lower() for time in texto.split()):
            return match_id, nome_jogo
    return None, None

def previsao_partida(match_id):
    headers = {"Authorization": f"Token {API_KEY}", "Accept": "application/json"}
    try:
        resp = requests.get(f"https://sports.bzzoiro.com/api/v1/predictions/matches/{match_id}", headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()["predictions"]
    except Exception as e:
        print(f"Erro: {e}")
        return None

def formatar_mensagem(nome_jogo, p):
    return (
        f"⚽️ {nome_jogo}\n"
        f"Casa: {p['home_win_prob']*100:.1f}% | Empate: {p['draw_prob']*100:.1f}% | Fora: {p['away_win_prob']*100:.1f}%\n"
        f"Confiança: {p['confidence_score']*100:.1f}%"
    )

async def consulta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.strip()
    match_id, nome_jogo = encontrar_jogo_por_nome(msg)
    if not match_id:
        await update.message.reply_text("Jogo não encontrado. Use nomes exatos dos times.")
        return
    p = previsao_partida(match_id)
    if not p:
        await update.message.reply_text("Não foi possível obter a previsão.")
        return
    await update.message.reply_text(formatar_mensagem(nome_jogo, p))

async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, consulta))
    await app.initialize()
    await app.start()
    print("Bot rodando...")
    try:
        while True:
            await asyncio.sleep(10)
    finally:
        await app.stop()
        await app.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
