# Analisador técnico B3 — versão online gratuita

Painel diário para múltiplas ações da B3, com coleta de candles diários do Yahoo Finance, motor técnico baseado no código avançado original e publicação automática de resultados.

## O que foi preservado do motor original

- MME 21 e MME 200 por média exponencial (`ewm`, `adjust=False`).
- True Range e ATR 14 por média móvel simples de 14 períodos.
- Velocidade = ATR14 / fechamento, com classificação por quantis dos últimos 60 registros válidos.
- Aceleração comparando MME21 e velocidade com o valor de cinco pregões atrás.
- Classificação de tendência com filtro de consolidação pela distância entre MME21 e MME200 em ATR.
- Ponto e Figura em janela de seis meses, caixa baseada em `ATR × 0,25` (mínimo de R$ 0,01) e reversão de três caixas.
- Alvo técnico pelo suporte/resistência P&F mais próximo válido e projeções de 1, 2 e 3 ATR.
- Estimativa mecânica de pregões = distância até o alvo / ATR14 atual. Essa estimativa não é previsão garantida.
- Backtest histórico do motor original: exige 220 pregões prévios, usa alvo P&F e stop de 1 ATR, verifica máximas/mínimas candle a candle, classifica conflitos como `AMBIGUO` e permite escolher o horizonte em pregões.

A interface e a coleta foram adaptadas para execução sem menus interativos. O código do motor foi extraído das funções do analisador avançado fornecido no projeto; o painel é uma camada nova de visualização.

## Arquivos

- `motor.py`: funções técnicas e função de backtest do analisador avançado.
- `atualizar.py`: coleta diária de vários tickers e grava o resultado.
- `app.py`: painel Streamlit.
- `ativos.txt`: lista de ações monitoradas, uma por linha.
- `.github/workflows/atualizar.yml`: agenda a execução às 21h30 UTC (18h30 em Brasília), de segunda a sexta, e permite execução manual.
- `dados/`: CSVs históricos e JSON consumido pelo painel.

## Implantação gratuita

A configuração usa **GitHub Actions** para executar a coleta e **Streamlit Community Cloud** para servir o painel. O caminho mais simples para manter tudo gratuito é um repositório público, mas isso deixa os CSVs, o histórico, a lista de ativos e o painel visíveis para outras pessoas. Não coloque dados privados, tokens ou informações pessoais no repositório. O Streamlit Community Cloud também documenta suporte a repositórios privados, com limites próprios para apps privados; confirme as condições atuais na sua conta se quiser manter o painel restrito.

### 1. Criar o repositório

1. Baixe e extraia o ZIP do projeto.
2. Entre em GitHub e crie um repositório novo, por exemplo `analisador-b3-online` (para o caminho gratuito mais simples, escolha público; não marque para criar README, pois o projeto já tem um).
3. Para enviar a pasta `.github/workflows` sem perder o arquivo de automação, recomendo usar o aplicativo gratuito GitHub Desktop: instale-o, clone o repositório recém-criado para o computador e copie para essa pasta clonada o conteúdo extraído do ZIP, incluindo a pasta oculta `.github`.
4. No GitHub Desktop, confirme as alterações, faça o commit para `main` e clique em **Push origin**.
5. Confirme no site do GitHub que `ativos.txt`, `motor.py`, `atualizar.py`, `app.py`, `requirements.txt` e `.github/workflows/atualizar.yml` estão nos locais indicados.

### 2. Configurar os ativos

Edite `ativos.txt`. Um ticker por linha, sem `.SA`, por exemplo:

```text
B3SA3
PETR4
VALE3
ITUB4
BBAS3
BBDC4
WEGE3
ABEV3
PRIO3
RENT3
```

Remova os exemplos que não quiser acompanhar e acrescente os tickers desejados. Salve e envie o commit para o GitHub.

### 3. Rodar a primeira coleta

1. No repositório, abra **Actions**.
2. Se o GitHub solicitar, habilite workflows.
3. Selecione **Atualizar analisador B3**.
4. Clique em **Run workflow** e confirme.
5. Abra a execução e confira os logs. Ao terminar, a pasta `dados/` deverá conter um CSV por ticker e `dados/analises.json` atualizado.

O agendamento automático é de segunda a sexta às 21h30 UTC (18h30 em Brasília). A agenda usa UTC e o GitHub pode atrasar o início; não é um serviço de execução com horário garantido. Feriados e dias sem pregão também podem executar, mas não devem criar candles novos.

### 4. Publicar o painel

1. Acesse https://share.streamlit.io/ e entre com sua conta GitHub.
2. Clique em **Create app**.
3. Selecione o repositório `analisador-b3-online`, branch `main` e arquivo principal `app.py`.
4. Clique em **Deploy**.
5. O Streamlit instalará as dependências de `requirements.txt` e fornecerá uma URL do painel.

O painel lê o JSON e os CSVs do próprio repositório. Cada execução do workflow publica novos dados por commit; o Streamlit pode levar um pouco para refletir as atualizações. Use o botão de atualização/reload do navegador se necessário.

### 5. Executar manualmente ou mudar horário

- Execução manual: GitHub → **Actions** → **Atualizar analisador B3** → **Run workflow**.
- Horário: edite o cron em `.github/workflows/atualizar.yml`. O cron é UTC; Brasília normalmente é UTC-3.

## Executar localmente para teste

Python 3.11 recomendado:

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate
pip install -r requirements.txt
python atualizar.py
streamlit run app.py
```

## Fonte e limitações

- A fonte de preços é o endpoint público do Yahoo Finance, não uma API oficial da B3. Pode haver atrasos, falhas, ajustes ou mudanças no serviço.
- O sistema usa candles diários, não monitora preços intradiários nem opções em tempo real.
- São exigidos pelo menos 220 pregões válidos para a análise, incluindo a MME200. Se um ticker falhar, o painel registra o erro sem impedir que os demais ativos sejam analisados.
- O cálculo de pregões estimados é uma aproximação mecânica baseada no ATR atual. Não leva em conta regime futuro de volatilidade, gaps ou eventos corporativos.
- O painel é informativo e não constitui recomendação de investimento. Valide os dados e as regras antes de tomar decisões.
