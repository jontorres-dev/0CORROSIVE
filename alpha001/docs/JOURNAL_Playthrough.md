# JOURNAL — Playthrough (Stage 2)

**Projeto:** Corrosive Engine  
**Início:** 2026-11-14  
**Responsável conceitual:** Betsy (Elisabeth, Designer de Produto)

## Por que este Journal

O Stage 2 é mais contrived que o Stage 1.  
Antes de reajustar World, GameMaster e demais eixos em função do Playthrough, priorizamos uma funcionalidade boa e estável do próprio Playthrough.  
Este Journal registra decisões, incrementos e o que permanece em aberto, para que o ajuste posterior seja consciente e mínimo.

## Estado atual (conceitos fechados)

- **RECOEF** como trinca funcional:  
  Relações (autor) + Condições mínimas (autor) + Efeitos possíveis (Progress propõe → GameMaster valida → World + notifica Cast).

- Flag nasce só de ação do Player (ou efeito já consolidado) e consolida-se por verossimilhança do GameMaster. Não fica pendente.

- Ciclo mínimo Flag → proposta → validação → commit está implementado e determinístico (Incremento 2).

- Condução opcional a ENDING / GAME_OVER está implementada (Incremento 3): só ocorre se o Módulo declarar Effect com `kind` especial e a Flag correspondente estiver consolidada. Caminho separado; não aborta Effects normais.

- Modifiers apenas em personagens, filhos de Flag. (ainda não implementado)

- Unlocks em dois graus (mesma run / próxima run somente se não houve GAME_OVER). (ainda não implementado)

- POV informado ao GameMaster é exclusivamente do Jogador. (ainda não implementado)

- Travas da LLM: sem Flag prévia não mata NPC, não aplica Modifier, não altera grafo de Flags/Progress.

Documentos de referência:  
- `bStorm_002.md`  
- `Playthrough_guia_minimo.md` (ótica DevOps)

## Próximo foco

Incrementos 1–3 do guia mínimo estão fechados.  
Ciclo Flag → Efeito → (opcional) fim de run está estável e determinístico.  
Próximos passos possíveis (ainda fora do núcleo): Modifiers simples, sinal de POV do Jogador, Unlocks.  
Qualquer reajuste amplo em World ou GameMaster só depois que o Playthrough central estiver consolidado.

## Registro de incrementos

*(a preencher conforme a implementação avança)*

### Incremento 1 — Flag + consolidação
- Status: fechado (2026-11-14)
- Notas: `Playthrough.py` (P maiúsculo) é o eixo do Stage 2. Modelo relacional: `Relation(id, subject, predicate, object)` é o molde. `Flag(id, source_action_id, relation_id)` só nasce se a Relação existe no Playthrough, ainda não foi consolidada, e o GameMaster confirmou verossimilhança; senão `None`. Não fica pendente. `consolidate_flag` (idempotente), `has_flag`, `flags_from_action`, `require_flag` (veto via `ActionDenied(WhyDeny.NO_FLAG)`). `Setting(playthrough, clock) -> dict` entrega `relations`, `flags` e `clock` para as camadas superiores lerem do mesmo lugar. Temporal (`valid_from`/`valid_until`) e flag_classes ficam como add-on depois. Stage 1 intacto; todos os kernels verdes. Sem Flag, efeito é vetado.

### Incremento 2 — RECOEF mínimo
- Status: fechado (2026-11-18)
- Notas: Ciclo mínimo Flag → proposta → validação → commit. Escolhas de formato mais simples:
  - Condition liga por `required_relation_id`. Cumprida quando existe Flag com aquele `relation_id`.
  - Effect é marcador (`id` + `payload`). Progress só propõe (`propose_effects` recebe `applied_effect_ids` para não repropôr).
  - GameMaster valida via `validate_effect` (reason estável: `"flag_consolidated"` / `"no_flag"`). Mesmo caminho para Proposal forçada.
  - Só `commit_approved_effect` escreve: adiciona id em `World.applied_effects` e notifica `Cast.notifications`. Idempotente.
  - RECOEF nunca escreve Flag nem Relation. Replay asserta que `flags` e `relations` permanecem iguais.
  - Módulo de teste dadaísta (1 Relation + 1 Condition + 1 Effect) vive no kernel de `Playthrough.py`.
  - Trilha observável: Proposal → EffectDecision (com motivo) → World/Cast commitados.
  - Stage 1 intacto. Determinismo: mesmo estado + mesma ação = mesmo resultado.

### Incremento 3 — Fim de run opcional
- Status: fechado (2026-11-18)
- Notas: Condução opcional a ENDING ou GAME_OVER. Escolhas de formato:
  - Declaração implícita: Effect com campo opcional `kind`. Valores reconhecidos: `"ENDING"` e `"GAME_OVER"`. Qualquer outro valor (ou `None`) é Effect normal.
  - Caminho separado: função pura `evaluate_run_end(playthrough, effects, applied_effect_ids) -> RunEndResult | None`. Devolve `RunEndResult(kind, effect_id)` somente se existe Effect com `kind` especial, a Flag da `required_relation_id` está consolidada, e o effect_id ainda não está em `applied_effect_ids`. Não chama `propose_effects` / `validate_effect` / `commit_approved_effect`.
  - `propose_effects` ignora Effects com `kind` especial, para que o caminho de fim não entre no ciclo normal.
  - Registro mínimo no World: `record_run_end(world, result) -> World` no GameMaster. Seta `World.run_end = result.kind` e adiciona o `effect_id` a `applied_effects`. Idempotente (se já registrado, devolve o mesmo World).
  - Ciclo RECOEF normal permanece intacto e pode gerar zero ou mais Effects. O passo de fim é chamado depois dos commits normais e não os aborta.
  - Sem soft lock, sem detecção de impossibilidade, sem geração automática de fim. Só conduz quando o Módulo declarou o Effect especial.
  - Teste de aceite no kernel de `Playthrough.py`: caso com Effect especial + Flag → resultado e registro em `World.run_end`; caso sem Effect especial → `None`; ambos coexistem no mesmo teste; Effects normais continuam; replay não duplica o fim nem altera o resultado; Playthrough não ganha Flag nem Relation nova.

## Guia mínimo original (referência)

**O que precisa existir**

1. **Flag básica**  
   Criação a partir de ação do Player que não existia no World inicial.  
   Consolidação por verossimilhança via GameMaster (não fica pendente).  
   Travas: LLM não mata NPC, não aplica Modifier e não altera grafo sem Flag prévia.

2. **RECOEF mínimo**  
   - Relações (autor)  
   - Condições mínimas (autor)  
   - Efeitos possíveis (Progress propõe → GameMaster valida → World + notifica Cast)  

   Sem árvore de tags. Progress só conduz se o Módulo declarar direção.

3. **Condução opcional a fim de run**  
   Capacidade de ir a ENDING ou GAME_OVER quando o Módulo declarar.  
   Se o Módulo não declarar, Progress permanece vazio/observador.

4. **Modifiers simples**  
   Apenas em personagens (Jogador ou NPC).  
   Filhos de Flag.

5. **Sinal de POV do Jogador**  
   Enxuto, só do Jogador, passado ao GameMaster.  
   NPCs ficam em Cast.

6. **Unlocks (pode entrar depois do primeiro ciclo)**  
   Dois graus: mesma run e próxima run (esta só se não houve GAME_OVER).

**Critério de “saiu do chão”**  
Um Módulo de teste declara um RECOEF curto.  
O Jogador realiza uma ação que cria Flag.  
O Progress propõe um efeito.  
O GameMaster valida.  
World e Cast refletem o resultado.  
Com ou sem ENDING/GAME_OVER.

**Fora deste guia**  
Formato visual das Relações, resolução de condições múltiplas, detalhes finos de derivação, expansões maiores de World/GameMaster.

Comece pelo 1–3. O resto encaixa em cima.

## Em aberto (não bloqueia o início)

- Formato visual das Relações.  
- Ação que satisfaz duas Condições mínimas.  
- Grau fino de derivação pela LLM.  
- Detalhes de exposição de POV no World/GameMaster.

---

Journal vivo. Atualizar a cada decisão ou incremento relevante do Stage 2.
