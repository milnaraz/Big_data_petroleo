import requests
import datetime
import pandas as pd
from io import BytesIO

def baixar_ultima_semana_csv_limpo():
    hoje = datetime.date.today()

    # Descobre o domingo da semana passada
    dias_ate_domingo = (hoje.weekday() + 1) % 7
    domingo_passado = hoje - datetime.timedelta(days=dias_ate_domingo + 7)
    sabado_passado = domingo_passado + datetime.timedelta(days=6)

    # Formata datas
    inicio_str = domingo_passado.strftime("%Y-%m-%d")
    fim_str = sabado_passado.strftime("%Y-%m-%d")

    # Monta URL do arquivo XLSX
    url = f"https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/arquivos-lpc/{domingo_passado.year}/revendas_lpc_{inicio_str}_{fim_str}.xlsx"
    nome_csv = f"revendas_lpc_{inicio_str}_{fim_str}.csv"

    try:
        # Baixa o arquivo XLSX diretamente na memória
        response = requests.get(url)
        response.raise_for_status()
        xlsx_bytes = BytesIO(response.content)
        df = pd.read_excel(xlsx_bytes)

        # Remove as 10 primeiras linhas
        df_limpo = df.iloc[9:]

        # Salva CSV sem cabeçalho e usando ; como separador
        df_limpo.to_csv(nome_csv, index=False, header=False, sep=';')
        print(f"Arquivo CSV '{nome_csv}' baixado e limpo com sucesso!")
    except requests.exceptions.RequestException as e:
        print(f"Erro ao baixar arquivo: {e}")
    except Exception as e:
        print(f"Erro ao processar o arquivo: {e}")

# Executa a função
baixar_ultima_semana_csv_limpo()

