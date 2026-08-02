# auto-job-apply

Biblioteca open-source para automação de candidaturas, extraída e refatorada a partir do [JobSpy](https://github.com/rodrigotxt/JobSpy).

## Objetivo
Fornecer uma interface unificada (`apply`) para automatizar a submissão de currículos em diversos sites de emprego, facilitando contribuições da comunidade.

## Principais características
- **Interface única:** `apply(site, url_vaga, dados, curriculo_path)`
- **Extensível:** Registro simples de novos sites.
- **Qualidade:** Foco em testes automatizados com DOM mockado.
- **Segurança:** Sem dados pessoais no repositório.
