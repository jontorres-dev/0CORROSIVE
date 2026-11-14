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

---

## 2026-11-12 — GameMode e avisos

- `GameMode(str, Enum)` no `GameMaster.py`, só com `EXPLORE`; dono único é o GameMaster. `read_mode()` devolve o modo atual. DIALOGUE descartado: sem uso por agora.
- `warn.py` (novo): `WhyWarn` (`PHASE_CHANGED`) e `PlayerWarning` (frozen, strict, `reason: WhyWarn`). Aviso não bloqueia; quem escreve a frase é a LLM.
- `check_phase(before, after)` no `GameMaster.py`: devolve `PHASE_CHANGED` quando o Tick vira o bloco, senão tupla vazia; nunca levanta erro.
- `test_imports.py`: passou a importar o `warn`.
- Kernels OK: Tick, Clock state, Verb, Deny, Door, Warn, GameMaster e Imports.
- Próximo: pacote de contexto da LLM.

---

## 2026-11-13 — Pacote de contexto da LLM

- `context.py` (novo): `NarrationContext` (frozen, strict, forbid) com `clock`, `phase`, `mode`, `status` e `warnings`. É a única coisa que a LLM recebe pra narrar; ela não lê o World direto.
- `build_context(before, after, application)`: monta o pacote com `read_phase`, `read_mode`, `application.status` e `check_phase`. Não decide nada novo, só junta.
- Testes: 11:30 + TOUCH → 12:30 AFTERNOON, EXPLORE, APPLIED e PHASE_CHANGED; 10:00 + TALK → sem avisos; mesmo tick de novo → DUPLICATE; pacote não aceita mudança depois de montado.
- `test_imports.py`: passou a importar o `context`.
- Kernels OK: Tick, Clock state, Verb, Deny, Door, Warn, GameMaster, Context e Imports.

---

## 2026-11-13 — Salas e RoomGlance

- Mensagens de erro do `text.py` traduzidas pro inglês. Moderação fora do escopo: o motor é de uso geral. `tick_unit` fica (útil pros outros modos), WAIT segue comentado, STOP fica com 25 por ora. Fim da run depois do dia 10 fica pra Playthrough.
- `Door` ganhou `rooms: tuple[str, str]`: a porta conhece as duas salas, e a tranca vale dos dois lados.
- `World` ganhou `rooms`, `doors` e `player_room`; o `apply_tick` repassa os três. `compose_world` agora exige salas, portas e sala inicial (os testes de relógio usam o mundo mínimo `"start"`).
- `glance.py` (novo): `Exit` (`door_id`, `leads_to`), `RoomGlance` (`room_id`, `exits`, `clock`) e `read_glance(world)`. A tranca não aparece no glance: o jogador só descobre testando.
- `NarrationContext` ganhou o campo `glance`, montado no `build_context` a partir do World depois do tick.
- `test_imports.py`: passou a importar o `glance`.
- Kernels OK: Tick, Clock state, Verb, Deny, Door, Warn, GameMaster, Context, Text, Glance e Imports.

---

## 2026-11-13 — Persistência e pipeline do turno

- `persistence.py` (novo): save só automático, sem comando de salvar. `SaveSlot` (`player_id`, `playthrough_id`, só letras, números e `-`) e `Snapshot` (`world_id` sha256 + `World`). Arquivos `data/<player>_<playthrough>_snapshot.json` e `_log.jsonl`, sempre em UTF-8.
- Erros próprios: `WhySaveFail` (`SLOT_EXISTS`, `SLOT_NOT_FOUND`, `WORLD_MISMATCH`) e `SaveError`. O WhyDeny não ganhou motivos novos.
- `new_game`, `load_game` (snapshot + replay do log; CONFLICT vira `WORLD_MISMATCH`, DUPLICATE passa), `record_tick` (autosave a cada turno, `snapshot_every=1`; confere se o mundo saiu do save) e `list_saves`.
- Roguelike: `RunEnd` (`DEATH`, `GAME_OVER`, `ENDING`). O `end_game` apaga o save e a próxima run começa do zero; o `playthrough_id` pode ser reusado.
- Revisão a fundo: path traversal, snapshot gravado por `.tmp` + troca atômica, arquivo corrompido, log órfão, mundo de outro save e arquivo estranho na pasta.
- `GameMaster.py`: `TurnResult` (`status`, `world`, `warnings`) e `run_turn` (verbo → `emit_tick` → `apply_tick` → `record_tick` → `check_phase`). Turno que não vale não salva nem avisa.
- Testes: 16 casos no persistence; no GameMaster, o turno APPLIED salvo, DUPLICATE, CONFLICT e `SLOT_NOT_FOUND`.
- `test_imports.py`: passou a importar o `persistence`.
- Kernels OK: Tick, Clock state, Verb, Deny, Door, Warn, GameMaster, Context, Text, Glance, Persistence e Imports.
- Próximo: MOVE (trocar de sala) e STOP sem tick.

---

## 2026-11-13 — MOVE

- `Tick` ganhou `door_id: str | None = None`: sem porta é só tempo; com porta é tempo + atravessar. O MOVE viaja dentro do tick, então o log e o replay do `load_game` refazem a troca de sala.
- `apply_tick`: DUPLICATE/CONFLICT comparam também o `door_id`. Porta inexistente ou de outra sala → `TARGET_NOT_FOUND`; trancada → `LOCKED`; senão `player_room` vira o outro lado da porta. O erro sobe antes de existir mundo novo.
- `emit_tick(verb, action_id, door_id)`: a saída é o objeto do MOVE. MOVE sem porta ou outro verbo com porta → `TARGET_NOT_FOUND`. `run_turn` repassa o `door_id`.
- MOVE negado não gera tick nem save. Sem inventário ainda: porta trancada sempre nega.
- Testes: ida e volta pela mesma porta, 25 min, save guarda a sala nova; LOCKED, porta inexistente, MOVE sem porta e TALK com porta negados sem gravar nada.
- Kernels OK: Tick, Clock state, Verb, Deny, Door, Warn, GameMaster, Context, Text, Glance, Persistence e Imports.
- Próximo: STOP sem tick.

