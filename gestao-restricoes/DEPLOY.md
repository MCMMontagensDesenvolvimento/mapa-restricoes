# Deploy corporativo do Lean Control

## Pré-requisitos

- domínio HTTPS para o frontend e a API;
- registro de aplicativo SPA e registro/exposição da API no Microsoft Entra ID;
- PostgreSQL 15 ou superior;
- aplicativo/identidade com acesso mínimo necessário ao site SharePoint;
- biblioteca contendo `Panorama_Semanal_Restricoes_Lean.xlsx`;
- cofre de segredos em produção.

Copie `.env.example` para `.env` somente no ambiente de execução. Não versione `.env`.

## Configuração do Microsoft Entra ID

1. Registre o frontend como SPA e adicione a URL HTTPS em **Redirect URIs**.
2. Registre ou exponha a API e crie o escopo `access_as_user`.
3. Autorize o frontend a solicitar esse escopo.
4. Crie grupos para Administrador, Editor e Visualizador e informe os IDs nas variáveis de ambiente.
5. Configure as permissões Graph com menor privilégio possível. Para acesso somente ao site necessário, avalie `Sites.Selected` e conceda acesso ao site explicitamente.
6. Conceda consentimento administrativo apenas após revisão da equipe de segurança.

SPAs não devem conter client secret. O fluxo configurado é Authorization Code com PKCE, conforme a [documentação Microsoft](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow).

## Execução local

1. Use `APP_ENV=development` e `DATABASE_URL=sqlite+aiosqlite:///./lean_control.db`.
2. Inicie a API na pasta `backend` com `uvicorn app.main:app --reload --port 8000`.
3. Configure `NEXT_PUBLIC_API_URL=http://localhost:8000/api` no `.env` local.
4. Inicie o frontend com `pnpm dev`.

O modo local aceita o usuário de desenvolvimento somente quando `APP_ENV=development` e nenhum token é enviado. Nunca use essa opção em produção.

## Servidor interno com Docker

1. Preencha `.env` com URLs HTTPS, IDs do Entra, PostgreSQL e SharePoint.
2. Defina `POSTGRES_PASSWORD` por secret do orquestrador ou arquivo protegido.
3. Execute `docker compose up -d --build`.
4. Coloque um reverse proxy corporativo na frente dos serviços e publique apenas HTTPS.
5. Direcione `/api` para a porta 8000 e o restante para a porta 3000.
6. Habilite backup do volume PostgreSQL, logs centralizados e monitoração de `/api/health`.

## Azure

Opção recomendada:

- Azure Container Apps ou App Service para frontend e API;
- Azure Database for PostgreSQL Flexible Server;
- Azure Key Vault para segredos;
- Application Insights/Log Analytics para observabilidade;
- Front Door ou Application Gateway para domínio, TLS e políticas de acesso.

Publique as imagens em Azure Container Registry. Injete configurações pelo serviço de hospedagem. Não copie `.env` para a imagem. Restrinja a rede do PostgreSQL e, quando possível, use Private Endpoint.

## SharePoint e sincronização

Configure `SHAREPOINT_DRIVE_ID` e o `ITEM_ID` do arquivo. O caminho é apenas alternativa de descoberta. O adaptador implementa localização, download, upload condicional com `If-Match`, consulta de versões e cópia de backup. A primeira sincronização deve rodar em modo de validação e produzir relatório antes de qualquer escrita.

O Graph permite baixar o conteúdo de um `driveItem`, substituir seu conteúdo, listar versões e criar cópias. Consulte [download](https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0), [upload](https://learn.microsoft.com/en-us/graph/api/driveitem-put-content?view=graph-rest-1.0), [versões](https://learn.microsoft.com/en-us/graph/api/driveitem-list-versions?view=graph-rest-1.0) e [cópia](https://learn.microsoft.com/en-us/graph/api/driveitem-copy?view=graph-rest-1.0).

## Publicação como PWA

Após o deploy HTTPS, abra o Lean Control no Edge ou Chrome e escolha **Instalar este site como aplicativo**. O manifesto, tema, ícone e service worker já estão preparados. As APIs e dados corporativos não são armazenados no cache offline.

## Página de entrada no SharePoint

1. Crie uma página moderna no site desejado.
2. Adicione o web part **Botão** ou **Link rápido**.
3. Defina o texto `ABRIR LEAN CONTROL`.
4. Informe a URL HTTPS publicada.
5. Configure abertura em nova guia, publique a página e valide com um usuário Visualizador.

O SharePoint atua apenas como portal de entrada; a API e o banco permanecem nos serviços corporativos.

## Launcher Windows

Na pasta `launcher`, altere `LeanControl.Launcher.json` com a URL e o health check corporativos. Execute `build-launcher.ps1` em uma máquina com .NET 8 para gerar `Lean Control.exe`. O executável consulta o health check, abre o navegador padrão e encerra. `Abrir Lean Control.bat` é a contingência sem executável.

## Checklist antes da migração

- validar mapeamento de todos os campos e IDs;
- revisar possíveis duplicidades de responsáveis;
- executar importação em ambiente de homologação;
- reconciliar contagens por status, responsável e área;
- testar edição simultânea e conflito 409;
- testar backup e restauração do Excel;
- testar perfis com contas reais;
- obter aprovação do responsável pelo dado antes da primeira escrita no SharePoint.

