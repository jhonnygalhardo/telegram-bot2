from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import aiohttp
import re

TELEGRAM_TOKEN = "SEU_TOKEN_AQUI"
API_URL = "https://sports.bzzoiro.com/api/v1/matches/today"  # Sua API de jogos

# Handler do /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Olá! Envie o jogo no formato 'TimeA x TimeB' que eu farei a análise automática."
    )

# Função que busca jogos do dia
async def buscar_jogos():
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(API_URL) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    print(f"Erro ao obter jogos do dia: {resp.status}")
                    return []
        except Exception as e:
            print(f"Erro na requisição da API: {e}")
            return []

# Função que encontra o jogo pelo nome (case insensitive)
def encontrar_jogo(jogos, time_a, time_b):
    for jogo in jogos:
        home = jogo.get("home_team", "").lower()
        away = jogo.get("away_team", "").lower()
        if (home == time_a.lower() and away == time_b.lower()) or \
           (home == time_b.lower() and away == time_a.lower()):
            return jogo
    return None

# Simulação de análise de probabilidades
def analisar_jogo(jogo):
    # Aqui você pode colocar a lógica de estatísticas reais
    # Exemplo simplificado baseado em odds da API
    home_odd = float(jogo.get("home_odd", 2.0))
    draw_odd = float(jogo.get("draw_odd", 3.0))
    away_odd = float(jogo.get("away_odd", 2.5))

    prob_home = round(100 / home_odd, 2)
    prob_draw = round(100 / draw_odd, 2)
    prob_away = round(100 / away_odd, 2)

    recomendacao = max(
        [("Vitória " + jogo["home_team"], prob_home),
         ("Empate", prob_draw),
         ("Vitória " + jogo["away_team"], prob_away)],
        key=lambda x: x[1]
    )

    return prob_home, prob_draw, prob_away, recomendacao[0], recomendacao[1]

# Handler das mensagens de texto
async def consulta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    padrao = re.compile(r"(.+?)\s*x\s*(.+)", re.IGNORECASE)
    match = padrao.match(texto)
    if not match:
        await update.message.reply_text("Formato inválido! Use: TimeA x TimeB")
        return

    time_a, time_b = match.groups()

    jogos = await buscar_jogos()
    if not jogos:
        await update.message.reply_text("Não foi possível obter os jogos do dia.")
        return

    jogo = encontrar_jogo(jogos, time_a, time_b)
    if not jogo:
        await update.message.reply_text(f"Jogo {time_a} x {time_b} não encontrado hoje.")
        return

    prob_home, prob_draw, prob_away, rec, rec_prob = analisar_jogo(jogo)

    resposta = (
        f"📊 Análise do jogo: {jogo['home_team']} x {jogo['away_team']}\n"
        f"- Probabilidade Vitória {jogo['home_team']}: {prob_home}%\n"
        f"- Probabilidade Empate: {prob_draw}%\n"
        f"- Probabilidade Vitória {jogo['away_team']}: {prob_away}%\n\n"
        f"💡 Recomendação: {rec} ({rec_prob}%)"
    )

    await update.message.reply_text(resposta)

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, consulta))

    print("✅ Bot iniciado e ouvindo mensagens...")
    app.run_polling()

if __name__ == "__main__":
    main()
