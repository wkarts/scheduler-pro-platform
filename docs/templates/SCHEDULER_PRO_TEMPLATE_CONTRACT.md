# Scheduler Pro Template Contract — SPTC v1

O **Scheduler Pro Template Contract (SPTC)** é o contrato oficial para criação, validação, importação, versionamento e distribuição de modelos visuais da plataforma.

Ele existe para impedir que uma nova Landing Page ou Página de Agendamento seja construída como um arquivo isolado que funciona apenas em um cliente, em uma resolução ou em uma versão específica do frontend.

## 1. Local único de importação

Todo novo modelo externo deve entrar pela mesma superfície administrativa:

**Control Plane → Modelos & Suporte → Importar Modelos**

A Central de Importação é o ponto canônico. O editor do cliente não importa arquivo bruto. Ele apenas consome modelos já validados e, quando necessário, cria uma cópia personalizada daquele modelo para o cliente.

Isso evita três fontes diferentes de verdade para Landing Page, Página de Agendamento e modelos globais.

## 2. Formato do arquivo

Nome recomendado:

`<chave>.scheduler-pro-template.json`

Schema obrigatório:

`"schema": "scheduler-pro-template-package/v1"`

Um pacote pode carregar:

- somente a Landing Page;
- somente a Página de Agendamento;
- **preferencialmente as duas superfícies da mesma família visual**.

Exemplo de família:

- `studio-beatriz-nails` / LANDING;
- `studio-beatriz-nails` / BOOKING.

A chave é igual nas duas superfícies. O banco mantém versões independentes para cada uma.

## 3. Estrutura do pacote

```json
{
  "schema": "scheduler-pro-template-package/v1",
  "package": {
    "key": "modelo-negocio-generico",
    "name": "Modelo de Negócio Genérico",
    "description": "Descrição do modelo",
    "segment": "generico",
    "scope": "INTERNAL",
    "default_for_new_tenants": false,
    "surfaces": {
      "landing": {},
      "booking": {}
    }
  }
}
```

Campos principais:

| Campo | Regra |
| --- | --- |
| `key` | minúsculas, números e hífen; 2 a 120 caracteres |
| `name` | nome comercial do modelo |
| `description` | finalidade do modelo |
| `segment` | agrupamento visual ou de negócio |
| `scope` | `GLOBAL`, `SELECTED`, `EXCLUSIVE` ou `INTERNAL` |
| `default_for_new_tenants` | só deve ser usado quando o modelo puder ser padrão para novos clientes |
| `surfaces.landing` | conteúdo da Landing Page |
| `surfaces.booking` | conteúdo da Página de Agendamento |

## 4. Escopos

### GLOBAL
Disponível para todos os clientes elegíveis.

### SELECTED
Disponível somente para os clientes escolhidos no Control Plane.

### EXCLUSIVE
Disponível para um único cliente.

### INTERNAL
Modelo interno ou em preparação. Não aparece para os clientes.

A importação de uma nova versão **não troca automaticamente a página que um cliente já usa**. A aplicação ao cliente é uma ação separada e auditável.

## 5. Contrato da Landing Page

Versão mínima para novos modelos: `2`.

Campos obrigatórios:

```json
{
  "version": 2,
  "global_styles": {},
  "seo": {},
  "blocks": []
}
```

### 5.1 Bloco

Cada bloco deve possuir:

```json
{
  "id": "hero-principal",
  "type": "hero",
  "props": {},
  "style": {},
  "responsive": {
    "desktop": {},
    "tablet": {},
    "mobile": {},
    "hidden": {
      "desktop": false,
      "tablet": false,
      "mobile": false
    }
  }
}
```

Regras:

- `id` estável e único no documento;
- `type` precisa existir no renderer público;
- `props` guarda conteúdo e comportamento editorial;
- `style` guarda apenas apresentação do bloco;
- `responsive` guarda diferenças por viewport;
- esconder um bloco deve ser feito por `responsive.hidden`, não removendo o bloco em runtime.

### 5.2 Tipos suportados

A fonte de verdade é o endpoint do contrato no Control Plane. Na versão atual são suportados, entre outros:

`hero`, `title`, `subtitle`, `text`, `logo`, `image`, `gallery`, `video`, `button`, `whatsapp_button`, `social`, `divider`, `spacer`, `card`, `cards`, `columns`, `grid`, `services`, `professionals`, `booking`, `calendar`, `form`, `business_hours`, `address`, `map`, `contact`, `faq`, `testimonials`, `cta`, `notices`, `policies`, `footer`.

Não criar tipos novos somente no JSON. Um novo tipo só é válido depois que o renderer público e o editor da plataforma suportarem esse tipo.

### 5.3 Integração com a Agenda

Modelos oficiais devem preferir um bloco explícito:

- `booking`;
- `calendar`;
- ou `form`.

Se nenhum deles existir, o renderer ainda injeta a agenda no final por compatibilidade, mas o validador gera orientação.

### 5.4 Serviços e profissionais

Blocos `services` e `professionals` não devem carregar uma cópia definitiva da base do cliente.

Eles são componentes dinâmicos e recebem os dados cadastrados no Scheduler Pro. O modelo define aparência, título e apresentação; o tenant define dados operacionais.

## 6. Contrato da Página de Agendamento

Versão mínima: `1`.

Campos obrigatórios:

```json
{
  "version": 1,
  "surface": "BOOKING",
  "global_styles": {},
  "layout": {},
  "copy": {}
}
```

### 6.1 `global_styles`

Cores recomendadas:

- `primary`;
- `secondary`;
- `accent`;
- `background`;
- `surface`;
- `text`;
- `muted`;
- `radius`.

`muted` é importante para subtítulos, explicações e textos auxiliares. Não usar contraste tão baixo que torne as informações apagadas.

### 6.2 `layout`

Valores atualmente reconhecidos:

- `service_selector`: `cards`, `select`, `compact`;
- `professional_selector`: `cards`, `select`, `compact`;
- `calendar`: `month_days`, `week_days`, `date_input`;
- `time_selector`: `chips`, `grid`, `select`;
- `customer_form`: `compact`, `stacked`, `cards`;
- `mobile_sticky_action`: booleano.

O modelo visual **não decide se Serviço, Profissional, Telefone, E-mail ou Tempo são obrigatórios**. Essa decisão pertence ao modelo de negócio/configuração da Agenda do cliente. Se um campo estiver desativado, a Página de Agendamento deve simplesmente deixar de exibi-lo.

### 6.3 `copy`

Campos recomendados/obrigatórios para novos modelos:

```json
{
  "eyebrow": "Agendamento online",
  "title": "Escolha seu horário",
  "subtitle": "Selecione o atendimento e a melhor disponibilidade.",
  "success": "Seu horário foi reservado."
}
```

Esses textos são aplicados pelo runtime da Página de Agendamento, sem duplicar código por modelo.

## 7. O que um modelo NÃO pode fazer

Um modelo não deve:

- incluir JavaScript arbitrário;
- depender de `onclick`, `onload` ou outro handler HTML;
- embutir credenciais, tokens ou segredos;
- chamar API interna diretamente;
- fixar IDs de serviço, profissional ou cliente de outro tenant;
- substituir regras de disponibilidade;
- ignorar as configurações de campos obrigatórios/opcionais;
- introduzir tipo de bloco que o renderer não reconhece;
- atualizar automaticamente a página publicada de um cliente;
- gravar dados fora do escopo do cliente.

HTML recebido como referência visual deve ser **convertido para o contrato de blocos**. O HTML bruto não é o artefato de implantação do modelo.

## 8. Processo recomendado para construir um novo modelo

1. Criar o layout visual em HTML/Figma/protótipo ou outra referência.
2. Separar conteúdo estático de conteúdo dinâmico.
3. Mapear cada seção para tipos suportados do renderer.
4. Criar `global_styles` e regras responsivas.
5. Criar a superfície LANDING.
6. Criar a superfície BOOKING com a mesma família visual.
7. Colocar ambas em um `scheduler-pro-template-package/v1`.
8. Abrir **Control Plane → Modelos & Suporte → Importar Modelos**.
9. Validar o pacote.
10. Corrigir todos os erros do contrato.
11. Escolher o escopo.
12. Importar como rascunho ou publicar na biblioteca.
13. Aplicar separadamente ao cliente desejado.
14. Personalizar logotipo, cores, textos, fotos, serviços e demais dados na cópia do cliente.
15. Publicar a versão do cliente somente depois da pré-visualização.

## 9. Versionamento

O par `surface + key` identifica o modelo.

Exemplo:

- LANDING / `studio-beatriz-nails` / v1;
- LANDING / `studio-beatriz-nails` / v2;
- BOOKING / `studio-beatriz-nails` / v1;
- BOOKING / `studio-beatriz-nails` / v2.

Importar novamente a mesma chave pode criar uma **nova versão**. A versão anterior continua preservada.

Um cliente que recebeu a v1 continua na v1 até que o administrador ou o próprio cliente aplique outra versão, conforme as permissões.

## 10. Personalização por cliente

Ao aplicar um modelo global, o Scheduler Pro cria uma configuração própria para o cliente. A partir desse momento, alterações de:

- logotipo;
- cores;
- textos;
- fotos;
- serviços;
- profissionais/responsáveis;
- contatos;
- horários;
- botões;
- redes sociais;
- regras da Agenda;

não modificam o modelo global original.

## 11. Validação em camadas

A mesma regra é aplicada em mais de um ponto para evitar divergência:

1. **Central de Importação** — valida o pacote completo antes da entrada na biblioteca;
2. **Catálogo global** — criação e nova versão são validadas por superfície;
3. **Landing Page** — rascunho/autosave são validados antes de persistir;
4. **Suporte do Control Plane** — aplicação de LANDING e BOOKING valida novamente a superfície;
5. **Publicação de versão global** — a versão é validada antes de ser publicada.

## 12. Checklist de homologação

Antes de liberar um modelo como oficial, verificar:

- [ ] pacote usa `scheduler-pro-template-package/v1`;
- [ ] chave é estável e reutilizada nas duas superfícies;
- [ ] Landing usa `version >= 2`;
- [ ] Booking usa `surface=BOOKING` e `version >= 1`;
- [ ] todos os blocos têm IDs únicos;
- [ ] todos os tipos existem no renderer público;
- [ ] existe integração clara com a Agenda;
- [ ] contraste de título, texto e `muted` está legível;
- [ ] desktop, tablet e mobile foram revisados;
- [ ] campos desativados na Agenda desaparecem corretamente;
- [ ] modelo não contém segredos nem scripts;
- [ ] importação não altera páginas em produção;
- [ ] nova versão não quebra clientes presos à versão anterior;
- [ ] aplicação exclusiva funciona para um cliente sem expor o modelo aos demais;
- [ ] a Página de Agendamento mantém a identidade da Landing sem duplicar regra de negócio.

## 13. Fonte de verdade executável

O backend expõe o contrato usado pela própria interface administrativa:

`GET /api/v1/platform/templates/contract`

Validação antes da importação:

`POST /api/v1/platform/templates/import/validate`

Importação:

`POST /api/v1/platform/templates/import`

A documentação humana e o contrato executável devem evoluir juntos.
