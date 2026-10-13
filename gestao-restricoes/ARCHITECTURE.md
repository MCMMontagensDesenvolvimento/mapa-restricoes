# Arquitetura corporativa do Lean Control

## Decisão recomendada

Adotar **PostgreSQL + Excel no SharePoint**.

O PostgreSQL é a fonte transacional do sistema. A planilha permanece como interface de interoperabilidade, importação, exportação e contingência. O serviço de sincronização consulta o `eTag` do arquivo antes de gravar, cria backup, compara versões e registra conflitos. Nenhuma divergência deve ser sobrescrita sem decisão explícita.

```text
Usuário corporativo
  → Microsoft Entra ID (SSO/PKCE)
  → Lean Control Web
  → API protegida e autorização por perfil
  → PostgreSQL (fonte operacional)
  → Serviço de sincronização
  → Microsoft Graph
  → Excel ou SharePoint List
```

## PostgreSQL + Excel no SharePoint

Vantagens:

- controle transacional, concorrência e índices adequados para muitos usuários;
- bloqueio otimista por `row_version` e conflitos HTTP 409;
- histórico completo independente do limite e do formato do Excel;
- relatórios, filtros e evolução futura mais previsíveis;
- Excel continua disponível para usuários e integrações existentes.

Desvantagens:

- requer banco, API, backup e monitoramento próprios;
- sincronização com Excel precisa de regras de precedência e homologação;
- operação tem mais componentes que uma solução somente Microsoft 365.

## SharePoint List + Excel para importação/exportação

Vantagens:

- administração integrada ao Microsoft 365;
- versionamento e permissões nativas;
- boa solução para formulários simples e volume moderado;
- menor infraestrutura inicial.

Desvantagens:

- consultas e paginação possuem particularidades do Graph/SharePoint;
- relacionamentos, auditoria analítica e evolução do domínio são menos flexíveis;
- listas muito largas ou com consultas não indexadas exigem cuidado;
- acoplamento maior ao SharePoint e à estrutura das colunas.

## Critério de decisão

Use PostgreSQL quando Lean Control for um sistema corporativo operacional, com reuniões simultâneas, histórico e evolução de integrações. Use SharePoint List quando a organização preferir uma solução Microsoft 365 de menor complexidade e aceitar limites funcionais. O adaptador `GraphClient.list_items()` permite uma prova controlada sem migrar dados automaticamente.

## Segurança e identidade

O frontend usa MSAL e fluxo Authorization Code com PKCE. A API valida assinatura, emissor e audiência do token. Perfis são derivados de grupos do Entra ID:

- Administrador: administração e sincronização;
- Editor: inclusão e alteração;
- Visualizador: leitura.

Segredos e connection strings existem apenas no ambiente de execução ou em um cofre. Para Azure, prefira Key Vault e identidade gerenciada sempre que o serviço escolhido suportar o fluxo.

## Referências técnicas

- [Microsoft identity platform: Authorization Code e PKCE](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow)
- [Microsoft Graph: baixar arquivo](https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0)
- [Microsoft Graph: atualizar arquivo](https://learn.microsoft.com/en-us/graph/api/driveitem-put-content?view=graph-rest-1.0)
- [Microsoft Graph: listar versões](https://learn.microsoft.com/en-us/graph/api/driveitem-list-versions?view=graph-rest-1.0)
- [Microsoft Graph: copiar arquivo e preservar histórico](https://learn.microsoft.com/en-us/graph/api/driveitem-copy?view=graph-rest-1.0)
- [Microsoft Graph: listar itens de uma SharePoint List](https://learn.microsoft.com/en-us/graph/api/listitem-list?view=graph-rest-1.0)

