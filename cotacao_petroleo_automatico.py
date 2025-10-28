"""
Script para baixar cotações USD/BRL do Investing.com
USA cloudscraper - Solução que FUNCIONA!
"""

import cloudscraper
import pandas as pd
from datetime import datetime, timedelta
import json

class InvestingDownloader:
    """Classe para baixar dados do Investing.com usando CloudScraper"""
    
    def __init__(self):
        self.base_url = "https://api.investing.com/api/financialdata/historical"
        self.pair_id = 8833  # USD/BRL
        
        # Criar scraper com CloudScraper (bypassa Cloudflare)
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'firefox',
                'platform': 'linux',
                'mobile': False
            }
        )
        
        # Headers ESSENCIAIS - domain-id é OBRIGATÓRIO!
        self.headers = {
            'domain-id': 'br',  # CRÍTICO! Sem isso retorna erro
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0',
            'Accept': '*/*',
            'Accept-Language': 'pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3',
            'Referer': 'https://br.investing.com/',
            'Origin': 'https://br.investing.com',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site'
        }
        
        self.scraper.headers.update(self.headers)
    
    def baixar_cotacoes(self, data_inicio, data_fim, intervalo='Weekly'):
        """
        Baixa cotações do Investing.com
        
        Args:
            data_inicio: string 'YYYY-MM-DD' ou objeto datetime
            data_fim: string 'YYYY-MM-DD' ou objeto datetime
            intervalo: 'Daily', 'Weekly' ou 'Monthly'
        
        Returns:
            DataFrame com as cotações ou None se falhar
        """
        
        # Converter datas se necessário
        if isinstance(data_inicio, datetime):
            data_inicio = data_inicio.strftime('%Y-%m-%d')
        if isinstance(data_fim, datetime):
            data_fim = data_fim.strftime('%Y-%m-%d')
        
        # Montar URL completa
        url = f"{self.base_url}/{self.pair_id}"
        
        # Parâmetros da requisição
        params = {
            'start-date': data_inicio,
            'end-date': data_fim,
            'time-frame': intervalo,
            'add-missing-rows': 'false'
        }
        
        print(f"📊 Baixando cotações USD/BRL ({intervalo})...")
        print(f"   Período: {data_inicio} até {data_fim}")
        
        try:
            response = self.scraper.get(url, params=params, timeout=30)
            
            print(f"   Status: {response.status_code}")
            
            # Verificar status
            response.raise_for_status()
            
            # Parse JSON
            dados = response.json()
            
            # Verificar se há erro
            if '@errors' in dados:
                print(f"❌ Erro da API: {dados['@errors']}")
                return None
            
            if 'data' not in dados or not dados['data']:
                print("⚠️ Nenhum dado retornado pela API")
                print(f"   Resposta: {dados}")
                return None
            
            # Converter para DataFrame
            df = pd.DataFrame(dados['data'])
            
            # Processar datas e valores
            if 'rowDateTimestamp' in df.columns:
                # Tentar detectar o formato (pode ser timestamp numérico ou ISO string)
                primeiro_valor = df['rowDateTimestamp'].iloc[0]
                
                if isinstance(primeiro_valor, str):
                    # Formato ISO string (ex: "2025-10-19T00:00:00Z")
                    df['Data'] = pd.to_datetime(df['rowDateTimestamp'])
                else:
                    # Timestamp numérico
                    df['Data'] = pd.to_datetime(df['rowDateTimestamp'], unit='s')
                    
            elif 'rowDate' in df.columns:
                df['Data'] = pd.to_datetime(df['rowDate'], unit='ms')
            else:
                print("⚠️ Coluna de data não encontrada")
                print(f"   Colunas: {df.columns.tolist()}")
                return None
            
            # Selecionar e renomear colunas principais
            colunas_disponiveis = {
                'last_close': 'Fechamento',
                'last_open': 'Abertura', 
                'last_max': 'Máxima',
                'last_min': 'Mínima',
                'volume': 'Volume'
            }
            
            colunas_finais = ['Data']
            for col_orig, col_nova in colunas_disponiveis.items():
                if col_orig in df.columns:
                    df[col_nova] = df[col_orig]
                    colunas_finais.append(col_nova)
            
            df = df[colunas_finais]
            
            # Converter valores numéricos (podem vir como string)
            colunas_numericas = ['Fechamento', 'Abertura', 'Máxima', 'Mínima']
            for col in colunas_numericas:
                if col in df.columns:
                    # Remover vírgulas e converter para float
                    if df[col].dtype == 'object':
                        df[col] = df[col].astype(str).str.replace(',', '.').astype(float)
            
            # Converter Volume (pode ter 'K' ou 'M')
            if 'Volume' in df.columns and df['Volume'].dtype == 'object':
                def converter_volume(v):
                    if pd.isna(v):
                        return 0
                    v = str(v).strip()
                    if 'M' in v:
                        return float(v.replace('M', '').replace(',', '.')) * 1_000_000
                    elif 'K' in v:
                        return float(v.replace('K', '').replace(',', '.')) * 1_000
                    else:
                        return float(v.replace(',', '.'))
                
                df['Volume'] = df['Volume'].apply(converter_volume)
            
            df = df.sort_values('Data').reset_index(drop=True)
            
            print(f"✅ {len(df)} registros baixados com sucesso!")
            return df
            
        except Exception as e:
            print(f"❌ Erro: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def baixar_ultimas_semanas(self, num_semanas=12):
        """Baixa cotações das últimas N semanas"""
        data_fim = datetime.now()
        data_inicio = data_fim - timedelta(weeks=num_semanas)
        
        return self.baixar_cotacoes(
            data_inicio.strftime('%Y-%m-%d'),
            data_fim.strftime('%Y-%m-%d'),
            intervalo='monthly'
        )
    
    def baixar_ultimo_ano(self, intervalo='Weekly'):
        """Baixa cotações do último ano"""
        data_fim = datetime.now()
        data_inicio = data_fim - timedelta(days=365)
        
        return self.baixar_cotacoes(
            data_inicio.strftime('%Y-%m-%d'),
            data_fim.strftime('%Y-%m-%d'),
            intervalo=intervalo
        )


def salvar_csv(df, nome='cotacoes_brent_oil.csv'):
    """Salva DataFrame em CSV"""
    if df is not None and not df.empty:
        df.to_csv(nome, index=False, encoding='utf-8-sig')
        print(f"💾 Arquivo CSV salvo: {nome}")
        return True
    return False


def salvar_excel(df, nome='cotacoes_brent_oil.xlsx'):
    """Salva DataFrame em Excel"""
    if df is not None and not df.empty:
        try:
            df['Data'] = df['Data'].dt.tz_localize(None)
            df.to_excel(nome, index=False, engine='openpyxl')
            print(f"💾 Arquivo Excel salvo: {nome}")
            return True
        except ImportError:
            print("⚠️ openpyxl não instalado. Execute: pip install openpyxl")
            return False
    return False


def salvar_json(df, nome='cotacoes_brent_oil.json'):
    """Salva DataFrame em JSON"""
    if df is not None and not df.empty:
        # Converter Data para string no formato ISO
        df_json = df.copy()
        df_json['Data'] = df_json['Data'].dt.strftime('%Y-%m-%d')
        
        with open(nome, 'w', encoding='utf-8') as f:
            json.dump(df_json.to_dict('records'), f, ensure_ascii=False, indent=2)
        
        print(f"💾 Arquivo JSON salvo: {nome}")
        return True
    return False


def mostrar_estatisticas(df):
    """Mostra estatísticas detalhadas das cotações"""
    if df is None or df.empty:
        return
    
    print("\n" + "="*60)
    print("📈 ESTATÍSTICAS DAS COTAÇÕES")
    print("="*60)
    
    print(f"\n📅 Período:")
    print(f"   Início: {df['Data'].min().strftime('%d/%m/%Y')}")
    print(f"   Fim:    {df['Data'].max().strftime('%d/%m/%Y')}")
    print(f"   Total:  {len(df)} registros")
    
    print(f"\n💵 Valores (Fechamento):")
    print(f"   Máxima:       R$ {df['Fechamento'].max():.4f}")
    print(f"   Mínima:       R$ {df['Fechamento'].min():.4f}")
    print(f"   Média:        R$ {df['Fechamento'].mean():.4f}")
    print(f"   Mediana:      R$ {df['Fechamento'].median():.4f}")
    print(f"   Último valor: R$ {df['Fechamento'].iloc[-1]:.4f}")
    
    # Calcular variação percentual
    primeira = df['Fechamento'].iloc[0]
    ultima = df['Fechamento'].iloc[-1]
    variacao = ((ultima / primeira) - 1) * 100
    
    print(f"\n📊 Variação no Período:")
    print(f"   Inicial:  R$ {primeira:.4f}")
    print(f"   Final:    R$ {ultima:.4f}")
    print(f"   Variação: {variacao:+.2f}%")
    
    if 'Volume' in df.columns and df['Volume'].notna().any():
        print(f"\n📦 Volume:")
        print(f"   Total:    {df['Volume'].sum():,.0f}")
        print(f"   Média:    {df['Volume'].mean():,.0f}")


def download_automatico_semanal():
    """
    Função exemplo para automação semanal
    Salva arquivo com data no nome
    """
    downloader = InvestingDownloader()
    
    # Baixar última semana (diário)
    hoje = datetime.now()
    uma_semana_atras = hoje - timedelta(days=7)
    
    df = downloader.baixar_cotacoes(
        uma_semana_atras.strftime('%Y-%m-%d'),
        hoje.strftime('%Y-%m-%d'),
        intervalo='Daily'
    )
    
    if df is not None:

        salvar_csv(df, nome_arquivo)
        print(f"\n✅ Backup semanal salvo: {nome_arquivo}")
        return True
    return False


# ============= EXEMPLO DE USO =============

if __name__ == "__main__":
    print("="*60)
    print("  DOWNLOAD AUTOMÁTICO - INVESTING.COM (USD/BRL)")
    print("  Usando CloudScraper (bypass Cloudflare)")
    print("="*60)
    print()
    
    # Criar downloader
    downloader = InvestingDownloader()
    
    # OPÇÃO 1: Baixar últimas 12 semanas (padrão)
    print("🔄 Baixando últimas 12 semanas...")
    df = downloader.baixar_ultimas_semanas(num_semanas=12)
    
    # OPÇÃO 2: Baixar último ano (descomente para usar)
    # df = downloader.baixar_ultimo_ano(intervalo='Weekly')
    
    # OPÇÃO 3: Período personalizado (descomente para usar)
    # df = downloader.baixar_cotacoes('2024-01-01', '2025-10-23', intervalo='Daily')
    
    # Processar resultados
    if df is not None:
        print("\n📋 Primeiros 5 registros:")
        print(df.head().to_string(index=False))
        
        print("\n📋 Últimos 5 registros:")
        print(df.tail().to_string(index=False))
        
        # Estatísticas
        mostrar_estatisticas(df)
        
        # Salvar em diferentes formatos
        print("\n" + "="*60)
        print("💾 SALVANDO ARQUIVOS")
        print("="*60)
        salvar_csv(df)
        salvar_excel(df)  # Requer: pip install openpyxl
        salvar_json(df)
        
        print("\n✅ Download concluído com sucesso!")
        
        # Exemplo de uso para automação
        print("\n" + "="*60)
        print("🤖 PARA AUTOMAÇÃO SEMANAL:")
        print("="*60)
        print("Descomente a linha abaixo no código:")
        print("# download_automatico_semanal()")
        
    else:
        print("\n❌ Não foi possível baixar os dados.")
        print("\n💡 VERIFICAÇÕES:")
        print("1. ✓ cloudscraper instalado? pip install cloudscraper")
        print("2. ✓ Conexão com internet OK?")
        print("3. ✓ Header 'domain-id' está configurado? (já está no código)")


# ============= INFORMAÇÕES =============
"""
DEPENDÊNCIAS:
pip install cloudscraper pandas openpyxl

POR QUE CLOUDSCRAPER?
--------------------
- Bypassa proteção Cloudflare automaticamente
- Mais simples que curl-cffi
- Não precisa de navegador como Selenium
- Funciona de forma confiável

AUTOMAÇÃO SEMANAL:
------------------
🪟 WINDOWS (Task Scheduler):
1. Agendador de Tarefas > Criar Tarefa Básica
2. Gatilho: Semanal (ex: Segunda-feira 9h)
3. Ação: python.exe "C:\\caminho\\script.py"

🐧 LINUX/MAC (Crontab):
crontab -e
0 9 * * 1 /usr/bin/python3 /caminho/script.py
(Executa toda segunda-feira às 9h)

OUTROS PARES DE MOEDAS:
-----------------------
Mude o self.pair_id para:
- USD/BRL: 8833 (padrão)
- EUR/BRL: 17
- GBP/BRL: 42089
- EUR/USD: 1
- BTC/USD: 1057391

Para descobrir novos IDs:
1. Acesse a página do par no Investing.com
2. Abra DevTools > Network
3. Clique em Download
4. Veja o ID na URL da requisição

HEADER CRÍTICO:
---------------
'domain-id': 'br'  ← SEM ISSO A API RETORNA ERRO!

O domain-id indica qual versão do site você está acessando:
- 'br' = Brasil (br.investing.com)
- 'www' = Internacional (www.investing.com)
- 'es' = Espanha, etc.
"""
