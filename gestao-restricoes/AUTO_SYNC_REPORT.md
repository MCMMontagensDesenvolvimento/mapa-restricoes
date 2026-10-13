# Relatório — sincronização automática Sistema → Banco → Excel

Data da verificação: 14/09/2026

## Causa encontrada

O frontend enviava `POST` e `PUT` para a API e o backend confirmava a transação no banco, mas esses endpoints nunca chamavam uma função de escrita no Excel. O único fluxo existente lia Excel → Banco pelo botão **Sincronizar Excel**. Portanto, a interface e o banco eram atualizados, mas a planilha não participava do salvamento.

## Fluxo anterior

`Salvar na interface → API → banco → histórico → mensagem de sucesso`

Não havia escrita, conferência, status ou fila do Excel.

## Fluxo após a correção

`Salvar → validar → banco + fila → Excel por ID Exclusiva → reabrir e conferir → histórico → interface`

Se o Excel estiver bloqueado ou indisponível, o banco permanece salvo, a fila fica pendente e o usuário recebe uma mensagem específica. Uma rotina automática tenta novamente a cada 60 segundos; o botão **Sincronizar Excel** também reconcilia a fila antes de importar Excel → Banco.

## Arquivos alterados

- `backend/app/sync_service.py`
- `backend/app/main.py`
- `backend/app/models.py`
- `backend/app/config.py`
- `app/page.tsx`
- `lib/api.ts`
- `.env.example`

## Funções e estruturas criadas

- `save_restriction`: ponto central de persistência no banco, fila, Excel, conferência e histórico.
- `write_excel`: localiza por `ID Exclusiva`, altera apenas as células mapeadas e confere o arquivo salvo.
- `find_row`: rejeita IDs duplicadas e nunca usa o número da linha como identidade.
- `copy_row`: preserva estilo e traduz as fórmulas de Aging e Dias p/ Prazo para novas linhas.
- `backfill_ids`: preenche IDs determinísticas nas linhas antigas que não possuíam chave, com backup anterior.
- `retry_pending` e `retry_worker`: fila durável e tentativa automática posterior.
- tabela `sync_queue` e campo `audit_events.excel_result`.
- endpoints `GET /api/sync/status` e `POST /api/sync/retry`.

## Testes realizados e resultados

- 123 linhas existentes receberam `ID Exclusiva`; backup completo criado antes da operação estrutural.
- Nova restrição criada pela API e conferida na linha 130 do Excel.
- Responsável alterado de Eduardo para Rubens e conferido diretamente no Excel.
- Prazo alterado de 14/09/2026 para 18/09/2026 e conferido diretamente no Excel.
- Área, ação, prioridade, status e observação alterados simultaneamente e conferidos diretamente no Excel.
- Fórmulas nas colunas O e P permaneceram como fórmulas após criação e múltiplas edições.
- Status `Concluída` gravado no banco e conferido diretamente no Excel.
- Arquivo bloqueado com acesso exclusivo durante uma edição: banco preservado, resposta `excelSync=pending` e fila com 1 item.
- Arquivo liberado e nova tentativa executada: 1 item sincronizado e fila retornou a zero.
- Exclusão lógica testada: registro permaneceu no banco e no Excel com status `Cancelada`, sem remoção física da linha.
- Reconciliação executada após as gravações originadas no sistema: 124 registros inalterados, zero atualizações e zero conflitos, confirmando que não houve loop Sistema → Excel → Sistema.
- Histórico do registro de teste: 11 eventos sincronizados e zero eventos pendentes após a recuperação da fila.
- TypeScript e módulos Python compilados sem erros.

## Confirmação

Uma alteração realizada pelo Lean Control foi salva e conferida diretamente no arquivo Excel.
