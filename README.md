# Previsão da Demanda de Etanol Hidratado com Modelos Multivariados

Este projeto tem como objetivo avaliar e comparar diferentes abordagens para a previsão da demanda de etanol hidratado, incluindo modelos estatísticos, métodos de aprendizado de máquina e arquiteturas de aprendizado profundo. A análise utiliza variáveis auxiliares de natureza econômica e operacional, além de técnicas de análise exploratória para investigação da relevância e importância das variáveis explicativas.

O repositório é baseado e adaptado a partir do trabalho desenvolvido por Ellizeu Sena, expandindo os experimentos e reproduzindo metodologias aplicadas ao problema de previsão de demanda no setor de biocombustíveis.

## Ambiente de desenvolvimento

### 1. Configuração inicial

```bash
cp .env.example .env      # ajuste o que for necessário
```

O `.env` já está no `.gitignore` — nunca versione segredos.


### 2. Pacote `classes`

Os modelos (`NARX`, `DA_RNN`, `TFT`, ...) vivem no repositório
[`ellizeurs/timeseries-forecasting`](https://github.com/ellizeurs/timeseries-forecasting),
clonado localmente como `classes/` (ignorado pelo git):

```bash
git clone --depth 1 https://github.com/ellizeurs/timeseries-forecasting.git classes
```



### Variáveis de ambiente

| Variável | Descrição | Padrão |
|---|---|---|
| `DATABASE_URL` | URL de conexão do SQLAlchemy | `sqlite:///database/data.db` |
| `JUPYTERLAB_HOST` / `JUPYTERLAB_PORT` | Endereço do servidor | `127.0.0.1` / `8888` |
| `JUPYTERLAB_TOKEN` | Token de acesso ao JupyterLab | — |
| `RANDOM_SEED` | Semente global de reprodutibilidade | `42` |
| `OPTUNA_N_TRIALS` | Trials do Optuna | `100` |
| `CHECKPOINT_DIR` / `LOG_DIR` | Pastas de artefatos | `checkpoints` / `logs` |
| `MPLBACKEND` | Backend do matplotlib | `Agg` |

## Referência

SENA, Ellizeu Rodrigues. *Impacto de Notícias Econômicas e Climáticas na Previsão Neural da Demanda de Etanol*. Orientador: José Manoel de Seixas. 2026. 173 f. Dissertação – Programa de Engenharia Elétrica, COPPE, UFRJ, Rio de Janeiro, 2026.

KROHA, Petr; ŠKOULA, Miroslav. Hurst Exponent and Trading Signals Derived from Market Time Series. In: INTERNATIONAL CONFERENCE ON ENTERPRISE INFORMATION SYSTEMS, 20., 2018, Funchal. Proceedings of the 20th International Conference on Enterprise Information Systems. SCITEPRESS - Science and Technology Publications, 2018. p. 371-378. DOI: 10.5220/0006667003710378.

PETRALIA, Adrien et al. Timestral. arXiv, out. 2026. DOI: 10.48550/arXiv.2610.37585. MISTRAL AI. Timestral-209M. Hugging Face, 2026. Disponível em: https://huggingface.co/mistralai/Timestral-209M. Acesso em: 17 nov. 2026.
