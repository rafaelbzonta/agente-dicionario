import os
import json
import datetime
import ollama
 
# ══════════════════════════════════════════════════════════
#                        CONFIGURAÇÕES 
# ══════════════════════════════════════════════════════════
CONFIG = {
    # ── Provedor: "ollama" | "openai" | "anthropic" (veja integrações abaixo)
    "provedor": "ollama",
 
    # ── Modelo a usar (troque sem mexer no resto do código)
    #    Ollama:    "llama3.2" | "gemma2" | "mistral" | "tinyllama"
    #    OpenAI:    "gpt-4o"   | "gpt-4o-mini"
    #    Anthropic: "claude-sonnet-4-20250514"
    "modelo": "llama3.2",
 
    # ── Chaves de API (deixe "" se usar Ollama local)
    "openai_api_key":    os.getenv("OPENAI_API_KEY", ""),
    "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", ""),
 
    # ── Comportamento
    "salvar_historico": True,          # salva consultas em historico.json
    "max_historico":    20,            # máximo de turnos na memória curto prazo
    "temperatura":      0.3,           # 0 = mais preciso | 1 = mais criativo
}
 
# ══════════════════════════════════════════════════════════
#                       SYSTEM PROMPT 
# ══════════════════════════════════════════════════════════
SYSTEM_PROMPT = """
Você é um dicionário inteligente bilíngue (Português/Inglês).
 
Quando o usuário digitar uma palavra ou expressão, responda SEMPRE neste formato:
 
PALAVRA: {palavra}
IDIOMA: {idioma detectado}
 
DEFINIÇÃO:
{definição clara e objetiva}
 
CLASSE GRAMATICAL: {substantivo, verbo, adjetivo, etc.}
 
EXEMPLOS:
  1. {exemplo em português}
  2. {exemplo em inglês}
 
SINÔNIMOS: {lista de sinônimos}
ANTÔNIMOS: {lista de antônimos, se houver}
 
TRADUÇÃO:
  PT → EN: {tradução}
  EN → PT: {tradução}
 
---
Se a palavra não existir ou estiver errada, sugira a correção mais provável.
Seja preciso, didático e conciso.
"""
 
# ══════════════════════════════════════════════════════════
#                       INTEGRAÇÕES 
# ══════════════════════════════════════════════════════════
 
def _chamar_ollama(mensagens: list) -> str:
    resposta = ollama.chat(
        model=CONFIG["modelo"],
        messages=mensagens,
        options={"temperature": CONFIG["temperatura"]},
    )
    return resposta["message"]["content"]
 
 
def _chamar_openai(mensagens: list) -> str:
    from openai import OpenAI  # pip install openai
    cliente = OpenAI(api_key=CONFIG["openai_api_key"])
    resposta = cliente.chat.completions.create(
        model=CONFIG["modelo"],
        messages=mensagens,
        temperature=CONFIG["temperatura"],
    )
    return resposta.choices[0].message.content
 
 
def _chamar_anthropic(mensagens: list) -> str:
    import anthropic  # pip install anthropic
    cliente = anthropic.Anthropic(api_key=CONFIG["anthropic_api_key"])
    # Anthropic separa system das mensagens
    system = next((m["content"] for m in mensagens if m["role"] == "system"), "")
    msgs = [m for m in mensagens if m["role"] != "system"]
    resposta = cliente.messages.create(
        model=CONFIG["modelo"],
        max_tokens=1024,
        system=system,
        messages=msgs,
    )
    return resposta.content[0].text
 
 
# Roteador de provedores — adicione novos aqui
PROVEDORES = {
    "ollama":    _chamar_ollama,
    "openai":    _chamar_openai,
    "anthropic": _chamar_anthropic,
}
 
# ══════════════════════════════════════════════════════════
#                      NÚCLEO DO AGENTE
# ══════════════════════════════════════════════════════════
 
historico: list[dict] = []
 
 
def consultar(palavra: str) -> str:
    historico.append({"role": "user", "content": palavra})
 
    # Limita o histórico em memória para não estourar o contexto
    msgs_recentes = historico[-CONFIG["max_historico"]:]
    mensagens = [{"role": "system", "content": SYSTEM_PROMPT}] + msgs_recentes
 
    provedor_fn = PROVEDORES.get(CONFIG["provedor"])
    if not provedor_fn:
        raise ValueError(f"Provedor '{CONFIG['provedor']}' não reconhecido. "
                         f"Opções: {list(PROVEDORES.keys())}")
 
    conteudo = provedor_fn(mensagens)
    historico.append({"role": "assistant", "content": conteudo})
 
    if CONFIG["salvar_historico"]:
        _salvar_log(palavra, conteudo)
 
    return conteudo
 
 
def _salvar_log(palavra: str, resposta: str):
    """Salva cada consulta em historico.json para referência futura."""
    log_path = "historico.json"
    entrada = {
        "data": datetime.datetime.now().isoformat(timespec="seconds"),
        "modelo": f"{CONFIG['provedor']}/{CONFIG['modelo']}",
        "palavra": palavra,
        "resposta": resposta,
    }
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entrada, ensure_ascii=False) + "\n")
    except IOError:
        pass  # falha silenciosa no log
 
 
# ══════════════════════════════════════════════════════════
#                     INTERFACE DE TERMINAL
# ══════════════════════════════════════════════════════════
 
def _cabecalho():
    print("=" * 55)
    print("  DICIONARIO |  PT / EN  ")
    print(f"  Modelo: {CONFIG['provedor']}/{CONFIG['modelo']}")
    print("=" * 55)
    print("  Comandos especiais:")
    print("    'sair'   — encerra o programa")
    print("    'limpar' — reseta o historico da conversa")
    print("    'modelo' — troca o modelo sem reiniciar")
    print("=" * 55 + "\n")
 
 
def _trocar_modelo():
    print(f"\n  Modelo atual: {CONFIG['provedor']}/{CONFIG['modelo']}")
    novo_provedor = input("  Provedor (ollama/openai/anthropic) [Enter = manter]: ").strip()
    novo_modelo   = input("  Modelo [Enter = manter]: ").strip()
    if novo_provedor:
        CONFIG["provedor"] = novo_provedor
    if novo_modelo:
        CONFIG["modelo"] = novo_modelo
    print(f"\n  Modelo atualizado: {CONFIG['provedor']}/{CONFIG['modelo']}\n")
 
 
def main():
    _cabecalho()
 
    while True:
        try:
            entrada = input("Palavra: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nAte logo!")
            break
 
        if not entrada:
            continue
 
        match entrada.lower():
            case "sair":
                print("\nAte logo!")
                break
            case "limpar":
                historico.clear()
                print("\nHistorico limpo!\n")
            case "modelo":
                _trocar_modelo()
            case _:
                print("\nConsultando...\n")
                try:
                    resultado = consultar(entrada)
                    print(resultado)
                except Exception as e:
                    print(f"\nErro ao consultar: {e}")
                print("\n" + "─" * 55 + "\n")
 
 
if __name__ == "__main__":
    main()
