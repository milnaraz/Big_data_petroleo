# %%
import pandas as pd
import cloudscraper
import requests
import json
from datetime import date, timedelta
from io import BytesIO, StringIO
import psycopg2
from sqlalchemy import create_engine
import matplotlib.pyplot as plt
import seaborn as sns

# %%
# Automatizar o download dos dados do investing (cotação do dolar e petroleo)

url_base = "https://api.investing.com/api/financialdata/historical"
id_dolar = 2103
id_petroleo = 8833

scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'firefox',
        'platform': 'linux',
        'mobile': False
    }
)

header_request = {
    'domain-id': 'br',
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0',
    'Accept': '*/*',
    'Accept-Language': 'pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3',
    'Referer': 'https://br.investing.com/',
    'Origin': 'https://br.investing.com',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site'
}

scraper.headers.update(header_request)
 
# Intervalo de datas
hoje = date.today()
dias_ate_domingo = (hoje.weekday() + 1) % 7
ultimo_domingo_valido = hoje - timedelta(days=dias_ate_domingo + 7)
ultimo_sabado_valido = ultimo_domingo_valido + timedelta(days=6)
data_final = hoje - timedelta(days= 14)


# %%
# Automatizar o download dos dados da ANP (preço dos combustíveis)
inicio_str = ultimo_domingo_valido
fim_str = ultimo_sabado_valido

df_combustiveis = pd.DataFrame()

while inicio_str >= data_final:
    try:
        url = ''
        if inicio_str <= date(2025, 10, 12):
            url = f"https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/arquivos-lpc/{inicio_str.year}/revendas_lpc_{inicio_str}_{fim_str}.xlsx"
        else:
            if(inicio_str == date(2025, 10, 19)):
                url = f'https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/arquivos-lpc/{inicio_str.year}/revendas_lpc.xlsx'
            else:    
                if inicio_str < date(2025, 11, 15):
                    diferenca_dias = inicio_str - date(2025, 10, 19)
                    id_url = int(diferenca_dias.days/7)
                    url = f'https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/arquivos-lpc/{inicio_str.year}/revendas_lpc-{id_url}.xlsx'
                else:
                    url = f"https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/arquivos-lpc/{inicio_str.year}/revendas_lpc-{(inicio_str + timedelta(days=1)).strftime('%d%m%Y')}-a-{(fim_str + timedelta(days=1)).strftime('%d%m%Y')}.xlsx"

        response = requests.get(url)
        response.raise_for_status()

        xlsx_bytes = BytesIO(response.content)
        df = pd.read_excel(xlsx_bytes)

        df.columns = df.iloc[8]
        df = df.iloc[9:]
        df = df.reset_index(drop=True)

        df_combustiveis = pd.concat([df_combustiveis, df], ignore_index=True)

    except Exception as e:
        print(f"Erro ao carregar de {inicio_str} a {fim_str}:\n {e}")

    finally:
        inicio_str -= timedelta(days=7)
        fim_str -= timedelta(days=7)

if not df_combustiveis.empty:
    df = df_combustiveis.copy()

    colunas_uteis = {
        'CNPJ': 'cnpj',
        'RAZÃO': 'razão_social',
        'FANTASIA': 'nome_fantasia',
        'ESTADO': 'estado',
        'MUNICÍPIO': 'municipio',
        'PRODUTO': 'produto',
        'PREÇO DE REVENDA': 'preco',
        'DATA DA COLETA': 'data_coleta'
    }

    colunas_finais_combustiveis = []
    for col_orig, col_nova in colunas_uteis.items():
        if(col_orig in df_combustiveis.columns):
            df_combustiveis[col_nova] = df_combustiveis[col_orig]
            colunas_finais_combustiveis.append(col_nova)

    df_combustiveis = df_combustiveis[colunas_finais_combustiveis]

    df_combustiveis = df_combustiveis[df_combustiveis['produto'] != 'GLP']

    df_combustiveis['cnpj'] = df_combustiveis['cnpj'].astype(str).str.replace(r'[^0-9]', '', regex=True).str.zfill(14)

    df_combustiveis = df_combustiveis.astype({
        'razão_social': 'string',
        'nome_fantasia': 'string',
        'estado': 'string',
        'municipio': 'string',
        'produto': 'string',
    })

    df_combustiveis['preco'] = pd.to_numeric(df_combustiveis['preco'], errors='coerce', downcast='float')

    df_combustiveis['data_coleta'] = pd.to_datetime(df_combustiveis['data_coleta'])

    #df_combustiveis.to_csv(f'arquivo_final.csv', index=False, header=True, sep=';')

    #print(df_combustiveis)

else:
    print('\n\nNenhum dado foi carregado')

# %%
# dados originais combustiveis
df.info()

# %%
# dataframe de combustiveis com as colunas finais
df_combustiveis.info()

# %%
df_combustiveis.describe()

# %%
try:
    # montar url para baixar cotação petroleo
    url = f"{url_base}/{id_petroleo}"

    data_inicio = ultimo_domingo_valido

    params_request = {
        'start-date': data_final,
        'end-date': data_inicio,
        'time-frame': 'Weekly',
        'add-missing-rows': 'false'
    }

    response = scraper.get(url, params=params_request, timeout=30)
    response.raise_for_status()

    dados = response.json()

    df_petroleo = pd.DataFrame(dados['data'])
    df = df_petroleo.copy()
    
    if not df_petroleo.empty:
        colunas_uteis = {
            'last_close': 'preco',
            'rowDate': 'data_cotacao',
            'volumeRaw': 'volume_transacoes'
        }

        colunas_finais_petroleo = []
        for col_orig, col_nova in colunas_uteis.items():
            if(col_orig in df_petroleo.columns):
                df_petroleo[col_nova] = df_petroleo[col_orig]
                colunas_finais_petroleo.append(col_nova)

        df_petroleo = df_petroleo[colunas_finais_petroleo]

        df_petroleo['preco'] = pd.to_numeric(df_petroleo['preco'].str.replace(',', '.'), errors='coerce').round(2).astype(float)

        df_petroleo['data_cotacao'] = pd.to_datetime(df_petroleo['data_cotacao'], format = '%d.%m.%Y')

        df_petroleo['volume_transacoes'] = df_petroleo['volume_transacoes'].astype(int)

        print(df_petroleo)

    else:
        print('Nenhum dado baixado')

except requests.exceptions.RequestException as e:
    print(f"Erro na requisição: {e}")

# %%
# Dados originais petroleo
df.info()

# %%
df_petroleo.info()

# %%
df_petroleo.describe()

# %%
try:
    # montar url para baixar cotação dolar
    url = f"{url_base}/{id_dolar}"

    data_inicio = ultimo_domingo_valido
    
    params_request = {
        'start-date': data_final,
        'end-date': data_inicio,
        'time-frame': 'Weekly',
        'add-missing-rows': 'false'
    }

    response = scraper.get(url, params=params_request, timeout=30)
    response.raise_for_status()

    dados = response.json()

    df_dolar = pd.DataFrame(dados['data'])
    df = df_dolar.copy()

    if not df_dolar.empty:
        colunas_uteis = {
            'last_close': 'preco',
            'rowDate': 'data_cotacao',
        }
        colunas_finais_dolar = []
        for col_orig, col_nova in colunas_uteis.items():
            if(col_orig in df_dolar.columns):
                df_dolar[col_nova] = df_dolar[col_orig]
                colunas_finais_dolar.append(col_nova)

        df_dolar = df_dolar[colunas_finais_dolar]

        df_dolar['preco'] = pd.to_numeric(df_dolar['preco'].str.replace(',', '.'), errors='coerce').round(4).astype(float)

        df_dolar['data_cotacao'] = pd.to_datetime(df_dolar['data_cotacao'], format = '%d.%m.%Y')

        print(df_dolar)
    
    else:
        print("Nenhum dado carregado")

except requests.exceptions.RequestException as e:
    print(f"Erro na requisição: {e}")

# %%
# Dados originais cotacoes dolar
df.info()

# %%
# dataframe com as colunas uteis
df_dolar.info()

# %%
df_dolar.describe()

# %%
conn = psycopg2.connect(
    dbname="predicao_combustiveis",
    user="postgres",
    password="postgres",
    host="localhost",
    port="5432"
)

cur = conn.cursor()

query = """
CREATE TABLE IF NOT EXISTS estado (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL UNIQUE,
    sigla CHAR(2) NOT NULL UNIQUE
);
"""
cur.execute(query)

query = """
CREATE TABLE IF NOT EXISTS cidade (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    estado_id INT NOT NULL, 
    CONSTRAINT fk_estado FOREIGN KEY (estado_id) REFERENCES estado(id)
);
"""
cur.execute(query)

query = """
CREATE TABLE IF NOT EXISTS posto (
    id SERIAL PRIMARY KEY,
    cnpj VARCHAR(14) NOT NULL UNIQUE,
    razao_social VARCHAR(100) NOT NULL,
    nome_fantasia VARCHAR(100) NULL,
    cidade_id INT NOT NULL, 
    CONSTRAINT fk_cidade FOREIGN KEY (cidade_id) REFERENCES cidade(id)
);
"""
cur.execute(query)

query = """
CREATE TABLE IF NOT EXISTS combustiveis (
    id SERIAL PRIMARY KEY,
    combustivel VARCHAR(30) NOT NULL UNIQUE
);
"""
cur.execute(query)

query = """
CREATE TABLE IF NOT EXISTS cotacao_combustiveis (
    id SERIAL PRIMARY KEY,
    posto_id INT NOT NULL,
    combustivel_id INT NOT NULL,
    preco NUMERIC(4, 2) NOT NULL,
    data_coleta DATE NOT NULL,
    CONSTRAINT fk_posto FOREIGN KEY (posto_id) REFERENCES posto(id),
    CONSTRAINT fk_combustivel FOREIGN KEY (combustivel_id) REFERENCES combustiveis(id),
    UNIQUE(posto_id, combustivel_id, preco, data_coleta)
);  
"""
cur.execute(query)

query = """
CREATE TABLE IF NOT EXISTS cotacao_dolar (
    id SERIAL PRIMARY KEY,
    preco NUMERIC(5, 4) NOT NULL,
    data_cotacao DATE NOT NULL
);
"""
cur.execute(query)

query = """
CREATE TABLE IF NOT EXISTS cotacao_petroleo (
    id SERIAL PRIMARY KEY,
    preco NUMERIC(4, 2) NOT NULL,
    data_cotacao DATE NOT NULL,
    volume_transacoes INT NOT NULL
);
"""
cur.execute(query)

query = """
INSERT INTO estado (nome, sigla) VALUES
    ('ACRE', 'AC'),
    ('ALAGOAS', 'AL'),
    ('AMAPA', 'AP'),
    ('AMAZONAS', 'AM'),
    ('BAHIA', 'BA'),
    ('CEARA', 'CE'),
    ('DISTRITO FEDERAL', 'DF'),
    ('ESPIRITO SANTO', 'ES'),
    ('GOIAS', 'GO'),
    ('MARANHAO', 'MA'),
    ('MATO GROSSO', 'MT'),
    ('MATO GROSSO DO SUL', 'MS'),
    ('MINAS GERAIS', 'MG'),
    ('PARA', 'PA'),
    ('PARAIBA', 'PB'),
    ('PARANA', 'PR'),
    ('PERNAMBUCO', 'PE'),
    ('PIAUI', 'PI'),
    ('RIO DE JANEIRO', 'RJ'),
    ('RIO GRANDE DO NORTE', 'RN'),
    ('RIO GRANDE DO SUL', 'RS'),
    ('RONDONIA', 'RO'),
    ('RORAIMA', 'RR'),
    ('SANTA CATARINA', 'SC'),
    ('SAO PAULO', 'SP'),
    ('SERGIPE', 'SE'),
    ('TOCANTINS', 'TO')
    ON CONFLICT DO NOTHING;
"""
cur.execute(query)

query = """
INSERT INTO combustiveis (combustivel) VALUES
    ('DIESEL S10'),
    ('GASOLINA COMUM'),
    ('DIESEL S500'),
    ('GNV'),
    ('ETANOL'),
    ('GASOLINA ADITIVADA')
    ON CONFLICT DO NOTHING;
"""
cur.execute(query)

conn.commit()

cur.close()
conn.close()

# %%
conn = psycopg2.connect(
    dbname="predicao_combustiveis",
    user="postgres",
    password="postgres",
    host="localhost",
    port="5432"
)

cur = conn.cursor()

if not df_combustiveis.empty:
    query = """
    CREATE TEMP TABLE IF NOT EXISTS dados_anp (
        cnpj VARCHAR(14) NULL,
        razao_social VARCHAR(100) NULL,
        nome_fantasia VARCHAR(100) NULL,
        cidade VARCHAR(100) NULL,
        estado VARCHAR(50) NULL,
        produto VARCHAR(50) NULL,
        preco NUMERIC(6, 2) NULL,
        data_coleta DATE NULL
    );
    """
    cur.execute(query)

    df_combustiveis_csv = StringIO()
    df_combustiveis[df_combustiveis['estado'] == 'MATO GROSSO DO SUL'].to_csv(df_combustiveis_csv, index=False, header=False, sep=';')
    df_combustiveis_csv.seek(0)

    cur.copy_from(
        df_combustiveis_csv,
        'dados_anp',
            sep=';',
            columns=('cnpj', 'razao_social', 'nome_fantasia', 'estado', 'cidade', 'produto', 'preco', 'data_coleta')
        )

    query = """
    INSERT INTO cidade (nome, estado_id) 
        SELECT DISTINCT cidade, estado.id 
            FROM dados_anp 
            JOIN estado ON estado.nome = dados_anp.estado 
        WHERE NOT EXISTS (SELECT 1 FROM cidade WHERE cidade.nome = dados_anp.cidade AND cidade.estado_id = estado.id) 
        ORDER BY 1;
    """
    cur.execute(query)

    query = """
    INSERT INTO posto (cnpj, razao_social, nome_fantasia, cidade_id) 
        SELECT  
            cnpj, 
            MAX(razao_social), 
            MAX(nome_fantasia), 
            cidade.id 
        FROM dados_anp 
        JOIN cidade ON cidade.nome = dados_anp.cidade 
        JOIN estado ON estado.nome = dados_anp.estado 
                        AND estado.id = cidade.estado_id
        WHERE 
            produto <> 'GLP' 
            AND NOT EXISTS (SELECT 1 FROM posto WHERE posto.cnpj = dados_anp.cnpj)
        GROUP BY cnpj, cidade.id;
    """
    cur.execute(query)

    query = """
    INSERT INTO cotacao_combustiveis (posto_id, combustivel_id, preco, data_coleta)
        SELECT posto.id, combustiveis.id, dados_anp.preco, dados_anp.data_coleta 
            FROM dados_anp 
            JOIN posto ON posto.cnpj = dados_anp.cnpj 
            JOIN combustiveis ON combustiveis.combustivel = dados_anp.produto 
        WHERE 
            dados_anp.estado = 'MATO GROSSO DO SUL'
            AND NOT EXISTS (
                SELECT 1 
                FROM cotacao_combustiveis 
                WHERE
                    cotacao_combustiveis.posto_id = posto.id
                    AND cotacao_combustiveis.combustivel_id = combustiveis.id
                    AND cotacao_combustiveis.preco = dados_anp.preco
                    AND cotacao_combustiveis.data_coleta = dados_anp.data_coleta
                )  
        ORDER BY 4;
    """
    cur.execute(query)


if not df_dolar.empty:
    query = """
    CREATE TEMP TABLE IF NOT EXISTS dados_dolar (
        preco NUMERIC(4, 2) NOT NULL,
        data_cotacao DATE NOT NULL
    );
    """
    cur.execute(query)

    df_dolar_csv = StringIO()
    df_dolar.to_csv(df_dolar_csv, index=False, header=False, sep=';')
    df_dolar_csv.seek(0)

    cur.copy_from(
        df_dolar_csv,
        'dados_dolar',
        sep = ';',
        columns = ('preco', 'data_cotacao')
    )

    query = """
    INSERT INTO cotacao_dolar (preco, data_cotacao)
        SELECT * 
        FROM dados_dolar
        WHERE 
            NOT EXISTS (
                SELECT 1    
                FROM cotacao_dolar
                WHERE
                    cotacao_dolar.preco = dados_dolar.preco
                    AND cotacao_dolar.data_cotacao = dados_dolar.data_cotacao
            )
        ORDER BY 2;
    """
    cur.execute(query)


if not df_petroleo.empty:
    query = """
    CREATE TEMP TABLE IF NOT EXISTS dados_petroleo (
        preco NUMERIC(4, 2) NOT NULL,
        data_cotacao DATE NOT NULL,
        volume_transacoes INT NOT NULL
    );
    """
    cur.execute(query)

    df_petroleo_csv = StringIO()
    df_petroleo.to_csv(df_petroleo_csv, index=False, header=False, sep=';')
    df_petroleo_csv.seek(0)

    cur.copy_from(
        df_petroleo_csv,
        'dados_petroleo',
        sep = ';',
        columns = ('preco', 'data_cotacao', 'volume_transacoes')
    )

    query = """
    INSERT INTO cotacao_petroleo (preco, data_cotacao, volume_transacoes)
        SELECT * 
        FROM dados_petroleo
        WHERE 
            NOT EXISTS (
                SELECT 1    
                FROM cotacao_petroleo
                WHERE
                    cotacao_petroleo.preco = dados_petroleo.preco
                    AND cotacao_petroleo.data_cotacao = dados_petroleo.data_cotacao
                    AND cotacao_petroleo.volume_transacoes = dados_petroleo.volume_transacoes
            )
        ORDER BY 2;
    """
    cur.execute(query)

conn.commit()

cur.close()
conn.close()

# %%
engine = create_engine('postgresql://postgres:postgres@localhost:5432/predicao_combustiveis')

df_cotacoes_combustiveis = pd.read_sql_query('SELECT * FROM view_cotacao_combustiveis', engine)

df_cotacoes_petroleo = pd.read_sql_query('SELECT * FROM cotacao_petroleo', engine)

df_cotacoes_dolar = pd.read_sql_query('SELECT * FROM cotacao_dolar ORDER BY 3', engine)

# %%
df_cotacoes_combustiveis.columns
df_cotacoes_dolar.columns

# %%
print(df_cotacoes_combustiveis)

# %%
print(df_cotacoes_petroleo)

# %%
print(df_cotacoes_dolar)

# %%
df_cotacoes_dolar = df_cotacoes_dolar.sort_values('data_cotacao')

plt.figure(figsize=(10, 6))
plt.plot(df_cotacoes_dolar['data_cotacao'], df_cotacoes_dolar['preco'], marker='o', linestyle='-', linewidth=2)
plt.xlabel('Data')
plt.ylabel('Preço (R$)')
plt.title('Evolução do Preço do Dólar ao Longo do Tempo')
plt.grid(True, alpha=0.3)
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()

# %%
df_cotacoes_petroleo = df_cotacoes_petroleo.sort_values('data_cotacao')

plt.figure(figsize=(10, 6))
plt.plot(df_cotacoes_petroleo['data_cotacao'], df_cotacoes_petroleo['preco'], marker='o', linestyle='-', linewidth=2)
plt.xlabel('Data')
plt.ylabel('Preço (R$)')
plt.title('Evolução do Preço do Barril de Petróleo ao Longo do Tempo')
plt.grid(True, alpha=0.3)
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()

# %%
media_cidades_comb = df_cotacoes_combustiveis.groupby(['cidade', 'combustivel'])['preco'].mean().unstack()

media_cidades_comb.plot(kind='bar', figsize=(12, 7))
plt.xlabel('Cidade')
plt.ylabel('Média de Preço')
plt.title('Média do Preço por Cidade e Combustível')
plt.legend(loc='upper left', bbox_to_anchor=(1, 1))
plt.tight_layout()
plt.show()

# %%
df_comb = df_cotacoes_combustiveis.rename(columns={
    'preco': 'preco_combustivel',
    'data_coleta': 'data'
})

df_dolar = df_cotacoes_dolar.rename(columns={
    'preco': 'preco_dolar',
    'data_cotacao': 'data'
})

# 🔧 Converter ambas para datetime
df_comb['data'] = pd.to_datetime(df_comb['data'])
df_dolar['data'] = pd.to_datetime(df_dolar['data'])

# Agora pode fazer o merge
df_merge = df_comb.merge(df_dolar, on='data')

fig, ax1 = plt.subplots(figsize=(12, 7))

# Linha do combustível (eixo esquerdo)
ax1.plot(df_merge['data'], df_merge['preco_combustivel'],
         label='Preço do Combustível', linewidth=2)
ax1.set_xlabel('Data')
ax1.set_ylabel('Preço do Combustível (R$)', color='blue')
ax1.tick_params(axis='y', labelcolor='blue')

# Linha do dólar (eixo direito)
ax2 = ax1.twinx()
ax2.plot(df_merge['data'], df_merge['preco_dolar'],
         label='Preço do Dólar', linestyle='--', linewidth=2)
ax2.set_ylabel('Dólar (R$)', color='green')
ax2.tick_params(axis='y', labelcolor='green')

plt.title('Relação entre Preço do Combustível e o Dólar')
plt.tight_layout()
plt.show()


# %%


# %%


import matplotlib.pyplot as plt

# Dados do KPI
df_kpi1 = kpi_ultimas_semanas[[
    'combustivel', 'preco_medio', 'n_registros'
]].copy()

df_kpi1['preco_medio'] = df_kpi1['preco_medio'].round(2)

fig, ax = plt.subplots(figsize=(10, len(df_kpi1)*0.6 + 1))
ax.axis('off')

tabela = ax.table(
    cellText=df_kpi1.values,
    colLabels=['Combustível', 'Preço Médio (R$)', 'Registros'],
    cellLoc='center',
    loc='center'
)

tabela.auto_set_font_size(False)
tabela.set_fontsize(11)
tabela.scale(1, 1.5)

# Estilo do cabeçalho
for (row, col), cell in tabela.get_celld().items():
    if row == 0:
        cell.set_facecolor('#E6E6E6')
        cell.set_text_props(weight='bold')

ax.set_title(
    'KPI 1 – Preço Médio Semanal dos Combustíveis',
    fontsize=14,
    pad=20
)

plt.tight_layout()
plt.show()

df_kpi2 = kpi_variacao[[
    'combustivel', 'preco_medio', 'variacao_pct'
]].copy()

df_kpi2['preco_medio'] = df_kpi2['preco_medio'].round(2)
df_kpi2['variacao_pct'] = df_kpi2['variacao_pct'].round(2)

fig, ax = plt.subplots(figsize=(10, len(df_kpi2)*0.6 + 1))
ax.axis('off')

tabela = ax.table(
    cellText=df_kpi2.values,
    colLabels=[
        'Combustível',
        'Preço Médio (R$)',
        'Variação (%)'
    ],
    cellLoc='center',
    loc='center'
)

tabela.auto_set_font_size(False)
tabela.set_fontsize(11)
tabela.scale(1, 1.5)

# Cabeçalho
for (row, col), cell in tabela.get_celld().items():
    if row == 0:
        cell.set_facecolor('#E6E6E6')
        cell.set_text_props(weight='bold')

ax.set_title(
    'KPI 2 – Variação Percentual Semanal',
    fontsize=14,
    pad=20
)

plt.tight_layout()
plt.show()
df_kpi3 = pd.DataFrame(resultados_alertas)[[
    'combustivel',
    'preco_medio',
    'limite_alerta',
    'taxa_alerta_pct'
]]

df_kpi3 = df_kpi3.round(2)

fig, ax = plt.subplots(figsize=(10, len(df_kpi3)*0.6 + 1))
ax.axis('off')

tabela = ax.table(
    cellText=df_kpi3.values,
    colLabels=[
        'Combustível',
        'Preço Médio (R$)',
        'Limite Alerta (R$)',
        '% Alertas'
    ],
    cellLoc='center',
    loc='center'
)

tabela.auto_set_font_size(False)
tabela.set_fontsize(11)
tabela.scale(1, 1.5)

for (row, col), cell in tabela.get_celld().items():
    if row == 0:
        cell.set_facecolor('#F2F2F2')
        cell.set_text_props(weight='bold')

ax.set_title(
    'KPI 3 – Taxa de Alertas (Preço > Média + 20%)',
    fontsize=14,
    pad=20
)

plt.tight_layout()
plt.show()
