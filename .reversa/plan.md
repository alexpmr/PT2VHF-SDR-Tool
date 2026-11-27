# Plano de Exploração — PT2VHF-SDR-Tool

> Criado pelo Reversa em 2026-11-27
> Marque cada tarefa com ✅ quando concluída.
> Você pode editar este plano antes de iniciar: adicione, remova ou reordene tarefas conforme necessário.

---

## Fase 1: Reconhecimento 🔍

- [x] ✅ **Scout** — Mapeamento de estrutura de pastas e tecnologias
- [x] ✅ **Scout** — Análise de dependências e gerenciadores de pacotes
- [x] ✅ **Scout** — Identificação de entry points, CI/CD e configurações

## Decisão de organização das specs 🗂️

> Entre o Scout e o Arqueólogo, o Reversa pergunta como você quer organizar as specs (por módulo, caso de uso, endpoint, híbrida, por features ou customizada). A escolha fica persistida em `.reversa/config.toml` na seção `[specs]` e não será reperguntada em execuções futuras. Para reapresentar o menu, remova manualmente a seção.

## Fase 2: Escavação 🏗️

- [x] ✅ **Arqueólogo** — Análise do módulo `sources`
- [x] ✅ **Arqueólogo** — Análise do módulo `dsp`
- [x] ✅ **Arqueólogo** — Análise do módulo `decoders`
- [x] ✅ **Arqueólogo** — Análise do módulo `engine`
- [x] ✅ **Arqueólogo** — Análise do módulo `scanner`
- [x] ✅ **Arqueólogo** — Análise do módulo `memory`
- [x] ✅ **Arqueólogo** — Análise do módulo `traffic`
- [x] ✅ **Arqueólogo** — Análise do módulo `ai_audio`
- [x] ✅ **Arqueólogo** — Análise do módulo `integrations`
- [x] ✅ **Arqueólogo** — Análise do módulo `ui`
- [x] ✅ **Arqueólogo** — Análise do módulo `app`

## Fase 3: Interpretação 🧠

- [x] **Detetive** — Arqueologia Git e ADRs retroativos ✅
- [x] **Detetive** — Regras de negócio implícitas e máquinas de estado ✅
- [x] **Detetive** — Matriz de permissões (RBAC/ACL) ✅
- [x] **Arquiteto** — Diagramas C4 (Contexto, Containers, Componentes) ✅
- [x] **Arquiteto** — ERD completo e integrações externas ✅
- [x] **Arquiteto** — Spec Impact Matrix ✅

## Fase 4: Geração 📝

- [x] **Redator** — Specs SDD por componente ✅
- [x] **Redator** — OpenAPI (se aplicável) ✅
- [x] **Redator** — User Stories (se aplicável) ✅
- [x] **Redator** — Code/Spec Matrix ✅

## Fase 5: Revisão ✅

- [ ] **Revisor** — Revisão cruzada de specs
- [ ] **Revisor** — Resolução de lacunas com o usuário
- [ ] **Revisor** — Relatório de confiança final

---

## Agentes Independentes

> Execute estes agentes quando os recursos estiverem disponíveis — podem rodar em qualquer fase.

- [ ] **Visor** — Análise de interface via screenshots
- [ ] **Data Master** — Análise completa do banco de dados
- [ ] **Design System** — Extração de tokens de design
- [ ] **Tracer** — Análise dinâmica (requer sistema acessível)

---

## Próximo passo

Após o Time de Descoberta concluir e o `_reversa_sdd/` estar populado, você pode disparar um dos fluxos seguintes:

- `/reversa-migrate`: orquestrador do **Time de Migração** (Paradigm Advisor → Curator → Strategist → Designer → Screen Translator → Inspector). Gera as specs do sistema novo. Saída em `_reversa_sdd/migration/` e `_reversa_sdd/screens/`.
- `/reversa-reconstructor`: gera plano bottom-up para reimplementar o software a partir das specs do legado (uma tarefa por sessão).
