# bStorm_001 — Camada LLM, economia de tokens e interface de ação

**Projeto:** Corrosive Engine (determinística)  
**Data:** 2026-11-09  
**Status:** brainstorm, nada implementado

---

## 1. Papel do Pydantic
- O Pydantic não é um modelo de LLM. Ele valida os dados da engine.
- Ele continua na arquitetura mesmo com a LLM: é o que barra uma resposta mal formada da LLM antes de ela chegar ao GameMaster.
- A escolha real é qual servidor local roda o modelo.

## 2. Servidor local de LLM
| Opção | Prós | Contras |
|---|---|---|
| **llama.cpp (`llama-server`)** | É o mais leve em memória, com controle total por CLI; tem API compatível com a da OpenAI e saída JSON por gramática ou schema | Pede mais configuração manual |
| **KoboldCpp** | Um executável só, bom para ficção interativa | Um pouco mais pesado por causa da interface web embutida |
| **Ollama** | É o mais simples de usar | É o menos econômico: mantém um serviço rodando, deixa o modelo carregado e às vezes reserva contexto demais. A experiência do usuário com ele foi "mais ou menos" |
| **LM Studio** | Tem uma interface gráfica boa | Não serve num servidor sem tela |

**Direção:** `llama-server` + Qwen2.5 3B Instruct Q4_K_M (já presente no computador, arquivo de ~2 GB), com contexto de 2048 e uso estimado em torno de 2,5 GB de RAM.  
O hardware de teste tem 8 núcleos, 15 GB de RAM e nenhuma GPU, então cabem modelos de 3B a 7B, e eles são lentos.  
O que mais pesa na memória é o modelo, não o servidor.

## 3. Direcionar a LLM e reduzir tokens (base)
- A LLM só vê o recorte da cena (`SceneGlance`), nunca o mundo inteiro. Ela não decide nada, só escreve.
- O prompt de sistema fica fixo e enxuto (tom, ponto de vista, regras, legenda de códigos, vozes dos NPCs). O `llama-server` guarda esse bloco em cache, então ele não é reprocessado a cada turno.
- **Memória resumida = flags do `Playthrough.py`**, não histórico bruto.
- A saída tem forma definida e um limite de tokens.
- A riqueza vem de dados curtos (marcas de voz e intenção de cena), não de volume.

Estimativa inicial: 500 a 800 tokens de entrada e 150 a 300 de saída por turno.

## 4. Meta: 30–40% desse volume
A meta é 200 a 300 tokens de entrada e 60 a 120 de saída por turno.
- **Delta em vez de cena inteira.** A sala completa vai só ao entrar nela; depois, só o que mudou.
- **Códigos curtos.** `R` = Raquel, `pn` = porta norte, com uma legenda fixa em cache. As flags entram como bits curtos (`conf+ trust3`).
- **Filtro de relevância.** O GameMaster manda só os NPCs e as flags pertinentes à ação.
- **Voz em cache.** No turno vai só o estado do momento (`R:curiosa`).
- **Saída sem envelope JSON.** Linhas `N: …` para a narração e `R: …` para a fala; a engine converte e valida depois.
- **Um beat por turno.** O GameMaster define (`beat:tensão_porta`) e a LLM encena.

O maior ganho vem de delta + cache.

## 5. Limite de input e opções de resposta
- **Limitar o input:** economiza pouco (cerca de 20 a 40 tokens). Serve como proteção, não como estratégia principal.
- **Opções estilo Baldur's Gate (3 a 5):** cortam forte, e podem ser geradas pela engine sem LLM. O risco é o jogo virar uma árvore de diálogo e deixar de ser sandbox.
- **Híbrido:** opções da engine mais um campo livre curto.

## 6. Proposta escolhida: interface estilo *Spaceship Warlock*
Campos de verbo clicáveis: **Toque**, **Fala**, **Aposento**, **Item**, **Sair** etc.

Fluxo:
1. O jogador clica no verbo. Por exemplo, em Toque (`T:`) aparecem os NPCs presentes.
2. Ele escolhe o alvo de uma lista fornecida pelo World, então não consegue inventar um alvo.
3. Uma caixa de texto com limite de caracteres recebe o "como".
4. Um **compilador** (parser determinístico) entende, normaliza, comprime e inclui a ação no delta.
5. O GameMaster valida e a LLM recebe uma entrada mínima, por exemplo: `T>R:"segura o pulso, firme"`.

Limites sugeridos por verbo:
| Verbo | Texto |
|---|---|
| Fala | ~120 caracteres |
| Toque / Item | ~60 caracteres |
| Aposento / Sair | nenhum, só o clique |

- O compilador mapeia termos comuns para tags (`firme`, `suave`, `hesita`) e guarda o texto original no log.
- Aposento e Sair podem devolver texto fixo vindo do Lore. A LLM só entra quando houver NPC reagindo ou uma mudança de cena que valha prosa.

## 7. Especificidade como mecânica
- Com o limite de caracteres, a precisão do input vira um controle nas mãos do jogador:
  - input específico: a ação sai próxima ou exatamente como ele pretendeu;
  - uma palavra só (por exemplo, uma parte do corpo): o modelo improvisa.
- Surpresas interessantes nascem desse espaço, e o jogador também pode brincar com essa margem.
- O compilador marca o grau de liberdade: `liv:alta` (`T>R:"pescoço"`) ou `liv:baixa` (frase detalhada).
- O improviso fica no **como**. O GameMaster garante o **o quê**, então o estado do mundo nunca quebra.

## 8. Mood e mecânicas no delta
- Como a ação ficou barata, o orçamento do delta vai para a textura: o mood do NPC, a tensão, a confiança e os modificadores do Playthrough.
- Formato curto: `R:mood=curiosa↑ tens=2 trust=3`.
- Entram só os campos que mudaram ou que pesam na ação atual.

---

## Em aberto
- Lista final de verbos e seus limites.
- Vocabulário de tags do compilador.
- Formato exato do delta e da legenda de códigos.
- `Tick`: o desenho será discutido antes de qualquer implementação.
