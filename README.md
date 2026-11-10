# Painel Diário Cometa

Painel que compara, todo dia às 07:00 (Cuiabá), os perfis de Instagram das concessionárias 4 rodas do Grupo Cometa e as avaliações dos perfis no Google Meu Negócio. A atualização roda sozinha no GitHub Actions, sem depender do Claude nem de nenhum computador ligado.

O painel mostra:
- **Instagram:** quantos posts cada perfil fez ontem, nos últimos 7 e nos últimos 30 dias, quantos dias teve post, a sequência de dias seguidos postando e uma grade de constância de 30 dias. Entram posts de feed e reels. Stories ficam de fora porque a API não os expõe.
- **Google:** nota média, total de avaliações, avaliações novas em 24 horas, 7 dias e 30 dias, e a variação da nota.

## Estrutura

| Arquivo | Para que serve |
|---|---|
| `config.json` | Lista das unidades (Instagram + link do Google). Edite aqui para incluir ou tirar perfis. |
| `scripts/coletar.py` | Coleta diária (API da Meta + Google Places API). |
| `scripts/montar_index.py` | Gera o `index.html` a partir de `src/painel.html`. |
| `src/painel.html` | Visual do painel. |
| `data/` | Histórico, gravado pela coleta. Não edite à mão. |
| `.github/workflows/atualizacao-diaria.yml` | Agendamento diário (11:00 UTC = 07:00 Cuiabá) e publicação no GitHub Pages. |

## Configuração (uma vez só)

### 1. Repositório e GitHub Pages
1. Suba esta pasta para um repositório no GitHub. Pode ser público ou privado. Num plano gratuito, o Pages só publica a partir de repositório público.
2. Em **Settings → Pages → Build and deployment → Source**, escolha **GitHub Actions**.

### 2. Token da Meta (Instagram)
A coleta usa o recurso *Business Discovery* da Graph API. Com ele, uma conta de Instagram comercial consulta os dados públicos de outras contas comerciais.

1. No [Meta for Developers](https://developers.facebook.com/apps), crie um app do tipo **Empresa** (ou use um que você já tenha) e conecte-o ao Business Manager do Grupo Cometa.
2. No **Business Manager → Configurações do negócio → Usuários → Usuários do sistema**, crie um usuário do sistema do tipo **Admin**. Em seguida:
   - atribua a ele o app e uma Página do Facebook que tenha uma conta de Instagram comercial conectada;
   - clique em **Gerar novo token**, escolha o app, defina a expiração como **Nunca** e marque as permissões `instagram_basic`, `pages_show_list`, `pages_read_engagement` e `business_management`.
3. Descubra o ID da conta de Instagram comercial ligada à Página. No Graph API Explorer, rode `GET /{id-da-página}?fields=instagram_business_account`. Esse número é o `IG_USER_ID`.

### 3. Chave da Google Places API
1. No [Google Cloud Console](https://console.cloud.google.com/), crie um projeto e ative o **faturamento**. O Google exige cartão cadastrado, mas cerca de 8 consultas por dia ficam dentro da cota gratuita mensal.
2. Em **APIs e serviços → Biblioteca**, ative a **Places API (New)**.
3. Em **Credenciais**, crie uma **chave de API** e restrinja-a à Places API (New).

### 4. Secrets do repositório
Em **Settings → Secrets and variables → Actions → New repository secret**, crie:

| Nome | Valor |
|---|---|
| `META_TOKEN` | o token do usuário do sistema |
| `IG_USER_ID` | o ID da conta de Instagram comercial |
| `GOOGLE_PLACES_KEY` | a chave da Places API |

### 5. Primeira execução
Na aba **Actions → Atualização diária → Run workflow**. A primeira coleta:
- já recupera os últimos ~60 posts de cada perfil, então a grade de 30 dias nasce preenchida;
- identifica cada perfil do Google pelo link de compartilhamento e guarda o ID em `data/places.json`.

A contagem de avaliações novas começa a partir desse dia.

Depois da primeira execução, confira na tabela do Google se o nome de cada perfil bate com a unidade. Se algum estiver errado, coloque o Place ID correto em `google_place_id` no `config.json`.

## Manutenção
- **Incluir uma unidade:** adicione um bloco em `config.json` e faça o commit. A coleta roda sozinha depois do push.
- **Coleta falhou:** o painel mostra um aviso amarelo no topo e a aba Actions mostra o erro.
- O GitHub pausa agendamentos de repositórios sem atividade por 60 dias. Os commits diários da coleta mantêm o repositório ativo.
