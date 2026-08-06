# Padrão de dados do candidato (dados_candidatura)

Todo site da biblioteca lê os dados do candidato do mesmo arquivo YAML
(`assets/dados-de-candidatura.yaml`) usando as chaves do **schema central**
(`src/auto_job_apply/schema.py`), todas em **inglês**.

## Por que um schema?

Formulários de emprego variam muito entre sites (inhire, quickin, gupy,
workable, greenhouse...). O schema concentra o maior número possível de
campos observados, organizados por seção:

| Seção | Campos (exemplos) |
|---|---|
| `personal` | `full_name`, `birth_date`, `gender`, `cpf`, `disabilities`, `photo_path` |
| `contact` | `email`, `phone`, `linkedin_url`, `github_url`, `portfolio_url` |
| `address` | `country`, `state`, `city`, `neighborhood`, `address`, `zip_code` |
| `professional` | `headline`, `desired_role`, `summary`, `skills`, `salary_expectation`, `contract_type`, `work_model`, `availability` |
| `diversity` | `gender_identity`, `sexual_orientation`, `race_ethnicity`, `disability_identity` |
| `application` | `referral`, `how_did_you_hear`, `cover_letter`, `consent`, `resume_path` |

Cada campo tem tipo (`str`, `int`, `float`, `bool`, `date`, `list`, `file`),
descrição, exemplo e — quando aplicável — valores aceitos (`opcoes`).

## Como os sites leem os dados

**Nunca** use `dados["chave_solta"]`. Use:

```python
from ..schema import obter, normalizar

dados = normalizar(dados)          # converte aliases pt→en
nome = obter(dados, "full_name")   # lê com default None
cargo = obter(dados, "desired_role", "Engenheiro(a) de Software")
```

- `normalizar()` converte aliases antigos em português (`nome` → `full_name`,
  `pretensao_salarial` → `salary_expectation`, ...) — YAMLs escritos antes do
  padrão continuam funcionando.
- `obter()` **sugere a criação** do campo se a chave não existir no schema:

```
[SCHEMA-SUGESTAO] campo 'driver_license_number' não existe no schema de
dados_candidatura. Para criá-lo: adicione em schema.py (SCHEMA) e declare em
`campos` no @register_site do site.
```

## Contribuindo com um site novo

1. **Declare os campos que o site usa** no decorator:

```python
@register_site("meu_site", campos=[
    "full_name", "email", "phone", "summary",
])
def apply_meu_site(engine, url_vaga, dados, curriculo_path) -> bool:
    ...
```

2. **Rode o check** para ver o que falta no YAML ou no schema:

```bash
make check-dados SITE=meu_site
```

Saída: cada campo do site com status (`ok` / `no-yaml` / `no-schema`) e duas
listas de sugestões:

- **criar no schema** — o site usa um campo que não existe no padrão:
  adicione o `Campo(...)` em `schema.py` e declare no `@register_site`.
- **preencher no YAML** — o campo existe no schema mas está vazio/ausente no
  seu `dados-de-candidatura.yaml`.

3. **Valide o YAML geral** (sem `--site`): erros de tipo, campo desconhecido,
   data fora do formato `dd/mm/aaaa` e obrigatórios ausentes (`full_name`,
   `email`) bloqueiam com exit 1.

## Validação

```bash
make check-dados              # valida o YAML contra o schema
make check-dados SITE=quickin # + campos que o quickin usa
```

A validação também roda de forma automática durante a candidatura: se o site
pedir um campo inexistente, o `obter()` loga `[SCHEMA-SUGESTAO]` apontando o
que criar.
