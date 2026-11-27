---
description: Índice da documentação do projeto e ritual obrigatório para manter os docs atualizados a cada entrega.
---

# Documentação

| Arquivo | Abra quando |
|---|---|
| [como-funciona.md](como-funciona.md) | quiser saber o que o sistema faz hoje: fontes, scripts, banco, relatórios, regras de dados |
| [adr/README.md](adr/README.md) | quiser o porquê das decisões de arquitetura |
| [backlog/README.md](backlog/README.md) | quiser saber o que falta fazer e em que ordem |
| [next-steps.md](next-steps.md) | quiser os próximos passos técnicos do repositório público |
| [entregas.md](entregas.md) | quiser o histórico do que foi entregue |

Como rodar os comandos: [../README.md](../README.md). Visão de arquitetura: [../ARCHITECTURE.md](../ARCHITECTURE.md). Regras para agentes: [../AGENTS.md](../AGENTS.md).

## Ritual de entrega (obrigatório)

Uma entrega só está pronta quando, **no mesmo commit** do código:

1. **[como-funciona.md](como-funciona.md)** descreve o novo estado (script novo, mudança de banco, regra de dados nova ou removida).
2. **O item sai do backlog:** apague a seção; se o arquivo do item ficar todo concluído, apague o arquivo e a linha dele em [backlog/README.md](backlog/README.md).
3. **[entregas.md](entregas.md)** ganha uma linha com data e o que foi entregue.
4. Se houve decisão de arquitetura, ela vira um ADR em [adr/](adr/README.md).
5. `README.md` da raiz muda se o jeito de rodar mudou.

O hook `.githooks/pre-commit` cobra os itens 1 e 3 sempre que o commit mexe em código, migrations ou dependências. Ative uma vez por clone com `git config core.hooksPath .githooks`. Para uma mudança sem efeito na documentação, use `SKIP_DOCS_CHECK=1 git commit`.

Nada de documentar o futuro no `como-funciona.md` nem o presente no backlog.
