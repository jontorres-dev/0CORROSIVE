# Diário de desenvolvimento — `World.py` (GameClock)

**Projeto:** Corrosive Engine (determinística)  
**Módulo:** `alpha001/ENGINE/deterministic/World.py`  
**Referência:** README — Backend Foundation (Architecture Amendment, 2026-11-08), §2.1 World e §6 Relógio e Sistema de Ticks

---

## 2026-11-08 — Corte 1: GameClock isolado

### Objetivo
Implementar o `GameClock` como estrutura isolada, pronta para ser composta pelo `World` e lida pelo GameMaster, com testes de kernel embutidos.

### Contrato de origem (outline §6)
```python
class GameClock(BaseModel):
    day: int
    hour: int
    minute: int
    tick_unit: str = "minute"
```
- World mantém o relógio.
- O avanço é autorizado exclusivamente pelo Game Master via `Tick`.
- A LLM não decide quanto tempo passou.

### Decisões
| Decisão | Motivo |
|---|---|
| Pydantic v2 com `frozen=True`, `strict=True`, `extra="forbid"` | Estado imutável e tipagem estrita; nenhum campo fora do contrato |
| Limites `day >= 1`, `hour 0–23`, `minute 0–59` | Estado temporal sempre válido na construção |
| `World` só com `clock: GameClock` e `read_clock()` | Ponto de injeção mínimo, sem antecipar outros eixos |
| Funções puras: `make_game_clock`, `read_clock_state`, `compose_world`, `is_valid_clock_state` | Determinismo; sem efeitos colaterais |
| Testes de kernel em `run_kernel_tests()` no próprio módulo | Pedido do escopo: testes embutidos |
| Sem `Tick` nem lógica de avanço | Fora do escopo; pertence ao GameMaster |

### Arquivos
- `alpha001/__init__.py`
- `alpha001/requirements.txt` — `pydantic>=2.0,<3`
- `alpha001/ENGINE/__init__.py`
- `alpha001/ENGINE/deterministic/__init__.py` — reexporta `GameClock`, `World`, `compose_world`, `make_game_clock`, `read_clock_state`
- `alpha001/ENGINE/deterministic/World.py`

### Ambiente
- Python 3.13 do sistema é gerenciado externamente (PEP 668); `pip install` global foi recusado.
- Solução: venv em `alpha001/.venv`; Pydantic 2.14.3 instalado nele.

### Cobertura dos testes de kernel
- Inicialização (dia 3, 14:00) e leitura de estado.
- `tick_unit` padrão `"minute"`.
- Bordas válidas: 1/00:00 e 1/23:59.
- Bordas inválidas recusadas: dia 0, hora 24 e −1, minuto 60 e −1.
- Tipagem estrita: `"3"` recusado; `True` recusado pelo validador puro.
- Campo extra recusado.
- Imutabilidade: atribuição em `clock.day` falha.
- Igualdade e hash estáveis entre instâncias equivalentes.
- `World.read_clock()` devolve a mesma instância injetada.

### Resultado
```
GameClock kernel tests: OK
```
Import pelo pacote (`from alpha001.ENGINE.deterministic import GameClock, World`) também verificado.

---

## 2026-11-08 — Ajustes de entrega
- Os `__init__.py` da raiz e de `ENGINE` estavam vazios (0 bytes) e passaram despercebidos; ganharam docstring de uma linha.
- Esclarecido: o nome é `__init__.py`, não `init.py`.
- Pacote entregue como `alpha001-engine.zip` (sem `.venv` e `__pycache__`).

## 2026-11-08 — Verificação do usuário
- Kernel executado pelo usuário: **OK**.

---

## 2026-11-09 — Corte 2: Tick e `World.apply_tick`

### Objetivo
Permitir que o `World` aplique um `Tick` emitido pelo GameMaster, de forma pura e idempotente, sem que uma resposta regenerada adicione tempo ao relógio.

### Implementado
- `Tick(amount: int >= 1, reason: str, source_action_id: str não vazio)`: frozen, strict, extra="forbid".
- `TickStatus` (Enum): `APPLIED`, `DUPLICATE`, `CONFLICT`.
- `TickApplication(status, world)`: resultado da aplicação.
- `World.applied_ticks: tuple[Tick, ...]`: o registro dos ticks pertence ao World.
- `World.apply_tick(tick) -> TickApplication`: função pura, que devolve um novo World.
  - `source_action_id` novo: avança o relógio, registra o tick e devolve `APPLIED`.
  - Mesmo id com o mesmo `amount` e `reason`: devolve `DUPLICATE` e o mesmo World.
  - Mesmo id com `amount` ou `reason` diferente: devolve `CONFLICT` e o mesmo World.
- `advance_clock(clock, minutes)`: normaliza minuto, hora e dia com `divmod`.

### Decisões
| Decisão | Motivo |
|---|---|
| Idempotência por `source_action_id` | Regenerar resposta (debug) nunca soma tempo; o bug já aconteceu antes |
| World imutável; retorna novo World | Sem alterações parciais |
| Conflito não altera estado | Mesmo id com dados diferentes é erro de quem emite, não do World |
| Registro em memória | Sem promessas de transação ou thread-safety nesta etapa |
| Sem novas dependências | Só Pydantic v2 |

### Cobertura dos testes (`run_tick_kernel_tests`)
- Tick novo aplicado; avanço exato; registro do tick.
- Duplicado: mesmo World, relógio intacto.
- Conflito por `amount` e por `reason`.
- Dois ids distintos aplicados em sequência.
- Virada de dia: dia 3, 23:50 + 20 min vira dia 4, 00:10.
- Ticks inválidos recusados: 0, −10, `True`, `"10"`, id vazio, id ausente, campo extra.
- `run_kernel_tests()` original segue inalterado e passando.

### Resultado
```
GameClock kernel tests: OK
Tick application kernel tests: OK
```
- Kernel verificado no meu computador e localmente pelo usuário: **OK**.
- Primeiro commit e push no GitHub: `World: GameClock + apply_tick idempotente com testes de kernel`.

---

## 2026-11-09 — Decisões de design do Tempo (acordadas, ainda não implementadas)

### Modos
- **Aproximação:** cada turno gera um Tick e o relógio avança.
- **Cena:** o relógio fica suspenso; dinâmicas resolvem ou prolongam a cena.

### Custo por verbo (minutos)
| Verbo | Custo |
|---|---|
| fala, sair, mudar_aposento (TALK, STOP, MOVE) | 25 |
| toque (TOUCH) | 60 |
| item, explorar (ITEM, SEARCH) | 45 |

### Saída de cena
- Piso de 40 min + 15 × n incrementos. A definição de "incremento" ainda está pendente.

### Blocos do dia (6 h cada)
| Bloco | Faixa |
|---|---|
| Manhã | 06:00–11:59 |
| Tarde | 12:00–17:59 |
| Noite | 18:00–23:59 |
| Madrugada | 00:00–05:59 |

- **Elipse:** salta para o início do próximo bloco.
- Ritmo da campanha: 3–4 blocos por dia, 8–15 turnos por bloco (até ~60 por dia), começando no meio da ação.

### Responsabilidades
- O GameMaster emite o Tick; só o World aplica.
- Tempo real está descartado.

---

## Pendente
- Normalizar verbos via Enum.
- `GameMode` como Enum (unificar nomes: APR/SCN vs aproximacao/cena).
- Distinguir verbo inválido de verbo com custo zero.
- Elipse: ler os blocos, tratar virada de dia e início exato de bloco.
- Dono único do modo (sugestão: World, mudando só por transição aprovada pelo GameMaster).
- Definir "incremento" da saída de cena.
- Emissão do Tick no GameMaster.
- Calendário; Salas, entidades, inventário, RoomGlance; Playthrough, Cast, Narrador, Lore.

---

## 2026-11-10

Tudo em `ENGINE/deterministic/`.

- Sync: `text.py`, `verbs.py`, `World.py` e `deny.py` iguais aos do usuário.
- Board de botões no lugar do parser (só decisão, sem arquivo).
- `verbs.py`: enum `Verb` com TALK, TOUCH, ITEM, SEARCH, MOVE e STOP. Sem LEAVE.
- `verbs.py`: `TXT_VERBS` com TOUCH, TALK e SEARCH, os que aceitam texto livre.
- `deny.py` (novo): enum `WhyDeny` e erro `ActionDenied(ValueError)`.
- `text.py`: `normalize_input` com Unicode NFD, tirando acentos e caixa ("Fála" vira "fala").
- Kernels OK:
  - GameClock: `World.py`, `run_kernel_tests`
  - Tick: `World.py`, `run_tick_kernel_tests`
  - Text: `text.py`, `run_kernel_tests`
  - Verb: `verbs.py`, `run_verb_kernel_tests`
  - Deny: `deny.py`, `run_errors_kernel_tests`

Decisões de design de hoje:

Botões listam só alvos existentes:
- Item: itens da sala
- Move: saídas da sala
- Touch: NPCs e o jogador
- Talk: NPCs

Texto livre:
- ActionDenied só nos de texto livre

Tempo:
- contador único do dia inteiro
- total do dia define o estágio (manhã, tarde, noite, madrugada)
- passou do total, vira o dia seguinte
- sai a lógica de cada bloco começar com +X
- Stop: sai do estado atual

Reorganização flow world

---

## 2026-11-11

- Repo: projeto no 0CORROSIVE (https://github.com/jontorres-dev/0CORROSIVE). Git roda sempre de dentro de `alpha001`.
- Limpeza: apagadas as pastas antigas do Ordo Aurea (`game`, `ordo`, `ordo-aurea-meretrix`); backup com o usuário.
- JSON: removidos `read_world_json`, `load_world_json`, o kernel JSON e o `sample_world.json`. Pasta `data/` fica vazia.
- Tempo: limite provisório de 10 dias, ainda sem regra no código. Clock e GameClock ficam como estão.
- Porta trancada: `door.py` (novo), modelo `Door` e regra `try_move`, que devolve a porta ou levanta `ActionDenied`.
- `deny.py`: entrou `WhyDeny.LOCKED`; kernel agora conta 3.
- `test_imports.py`: passou a importar o `door`.
- Kernels OK: Clock, Tick, Clock state, Text, Verb, Deny, Door e Imports.
- Próximo: mecânicas do GameMaster.
- Custos revistos para 25/60/45 min (TOUCH 1h): 8–15 turnos por bloco de 360 min, até ~60 por dia.
- `DayPhase` renomeado para MORNING, AFTERNOON, EVENING e NIGHT, batendo com os blocos.

---

## 2026-11-11 — GameMaster

- `GameMaster.py` (novo): `VERB_COST` (TALK/MOVE/STOP 25, TOUCH 60, ITEM/SEARCH 45), `emit_tick` (verbo + action_id → Tick) e `read_phase` (hora → bloco do dia).
- Elipse: `BLOCK_STARTS` (0, 6, 12, 18), `minutes_to_next_block` (minutos até o próximo início, nunca 0) e `emit_ellipse` (Tick com `reason="ellipse"`, passa pelo mesmo `apply_tick`).
- Testes: custo de cada verbo, bordas de fase, Tick de ponta a ponta no World (APPLIED e DUPLICATE) e elipse (11:30 → 12:00, 23:10 → dia 2 00:00).
- `test_imports.py`: passou a importar o `GameMaster`.
- Kernels OK: Tick, Clock state, Verb, Deny, Door, GameMaster e Imports.
- Próximo: GameMode.
