import pandas as pd
import requests
import streamlit as st
from datetime import datetime, timedelta

# --- Função para buscar a taxa Selic diária (código 11) ---
@st.cache_data(ttl=3600)
def get_selic_data_daily(start_date, end_date):
    """
    Busca a taxa Selic diária (código 11) do Banco Central para um período.
    Retorna um DataFrame com a data e o valor da Selic diária.
    """
    series_code = 11
    
    # Formata as datas para a requisição da API
    start_date_str = start_date.strftime('%d/%m/%Y')
    end_date_str = end_date.strftime('%d/%m/%Y')
    
    # A API para o código 11 tem um limite de 10 anos.
    # Vamos garantir que a data inicial esteja dentro desse limite.
    max_start_date = datetime.now() - timedelta(days=365 * 10)
    if start_date < max_start_date:
        start_date = max_start_date
        start_date_str = start_date.strftime('%d/%m/%Y')
    
    url_json = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{series_code}/dados?formato=json&dataInicial={start_date_str}&dataFinal={end_date_str}"
    
    try:
        response = requests.get(url_json)
        response.raise_for_status()
        
        data = response.json()
        df = pd.DataFrame(data)
        
        # Converte a coluna 'data' para o tipo datetime e o valor para numérico
        df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y')
        df['valor'] = pd.to_numeric(df['valor'])
        
        # Renomeia as colunas para clareza
        df.columns = ['Data', 'Selic % ao dia']
        st.info("Dados da Selic diária obtidos com sucesso via API JSON.")
        return df
    
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao buscar os dados da Selic: {e}")
        print(f"Erro na requisição da API do Banco Central: {e}")
        return None

# --- Função de cálculo de juros compostos diários com aportes e IR ---
def calculate_compounding_with_daily_data(principal, monthly_deposit, ir_rate, selic_df):
    """
    Simula o crescimento de um investimento com base nas taxas Selic diárias,
    considerando aportes mensais e o Imposto de Renda.
    Retorna um DataFrame com resultados diários.
    """
    if selic_df is None or selic_df.empty:
        return pd.DataFrame()
    
    df = selic_df.copy()
    
    current_value = float(principal)
    total_invested = float(principal)
    
    daily_results = []
    
    # Simulação diária
    for index, row in df.iterrows():
        date = row['Data']
        
        # Adiciona o aporte no primeiro dia do mês, mas apenas se não for o primeiro dia da série
        if len(daily_results) > 0 and date.day == 1:
            current_value += monthly_deposit
            total_invested += monthly_deposit
        
        # Aplica a taxa de juros diária diretamente
        current_value *= (1 + row['Selic % ao dia'] / 100)
        
        rendimento_bruto = current_value - total_invested
        ir_a_pagar = rendimento_bruto * (ir_rate / 100)
        valor_liquido = current_value - ir_a_pagar
        
        daily_results.append({
            'Data': date,
            'Valor Bruto': current_value,
            'Rendimento Bruto': rendimento_bruto,
            'IR a Pagar': ir_a_pagar,
            'Valor Líquido': valor_liquido
        })
    
    return pd.DataFrame(daily_results)

# --- Funções para criar tabelas de resumo (mensal e anual) ---
def create_monthly_table(daily_df):
    """
    Cria uma tabela resumida por mês a partir dos resultados diários.
    """
    df = daily_df.copy()
    df['Ano/Mês'] = df['Data'].dt.strftime('%Y-%m')
    
    # Agrupa por mês e pega o último valor do mês
    monthly_df = df.groupby('Ano/Mês').tail(1).reset_index(drop=True)
    
    return monthly_df[['Ano/Mês', 'Valor Bruto', 'Rendimento Bruto', 'IR a Pagar', 'Valor Líquido']]

def create_annual_table(daily_df):
    """
    Cria uma tabela resumida por ano a partir dos resultados diários.
    """
    df = daily_df.copy()
    df['Ano'] = df['Data'].dt.year
    
    # Agrupa por ano e pega o último valor do ano
    annual_df = df.groupby('Ano').tail(1).reset_index(drop=True)
    
    return annual_df[['Ano', 'Valor Bruto', 'Rendimento Bruto', 'IR a Pagar', 'Valor Líquido']]

# --- Configuração da Aplicação Streamlit ---
st.set_page_config(layout="wide")
st.title("Simulador de Investimento com a Taxa Selic")
st.markdown("Esta aplicação simula o valor de um investimento inicial com juros compostos diários, usando a taxa Selic de cada dia de 2020 até o presente.")

# Campos de entrada
with st.container():
    valor_inicial = st.number_input(
        'Digite o valor inicial do investimento:',
        min_value=0.0,
        value=1000.0,
        step=100.0,
        format="%.2f"
    )

    aporte_mensal = st.number_input(
        'Digite o valor do aporte mensal (opcional):',
        min_value=0.0,
        value=100.0,
        step=10.0,
        format="%.2f"
    )

    ir_rate = st.selectbox(
        'Selecione a alíquota de Imposto de Renda sobre os rendimentos:',
        options=[22.5, 20.0, 17.5, 15.0],
        index=3,
        format_func=lambda x: f'{x}% (a depender do prazo do investimento)'
    )

# Botão para atualizar a tabela
if st.button('Calcular'):
    with st.spinner('Buscando e calculando os dados...'):
        # Define o período (data de início em 2020)
        end_date = datetime.now()
        start_date = datetime(2020, 1, 1)
        
        # 1. Busca os dados da Selic diariamente
        selic_data_diaria = get_selic_data_daily(start_date, end_date)
        
        if selic_data_diaria is not None:
            # 2. Cria a tabela com o cálculo do investimento
            tabela_diaria = calculate_compounding_with_daily_data(valor_inicial, aporte_mensal, ir_rate, selic_data_diaria)
            
            if not tabela_diaria.empty:
                # 3. Exibe a tabela final no Streamlit
                st.subheader("Resultados Diários Detalhados")
                st.write(f"Valor inicial do investimento: **R${valor_inicial:.2f}**")
                st.write(f"Aporte mensal: **R${aporte_mensal:.2f}**")
                
                st.dataframe(
                    tabela_diaria.style.format({
                        'Valor Bruto': "R${:.2f}",
                        'Rendimento Bruto': "R${:.2f}",
                        'IR a Pagar': "R${:.2f}",
                        'Valor Líquido': "R${:.2f}"
                    }),
                    use_container_width=True
                )
                
                # 4. Cria e exibe a tabela mensal
                st.subheader("Resumo Mensal")
                tabela_mensal = create_monthly_table(tabela_diaria)
                st.dataframe(
                    tabela_mensal.style.format({
                        'Valor Bruto': "R${:.2f}",
                        'Rendimento Bruto': "R${:.2f}",
                        'IR a Pagar': "R${:.2f}",
                        'Valor Líquido': "R${:.2f}"
                    }),
                    use_container_width=True
                )

                # 5. Cria e exibe a tabela anual
                st.subheader("Resumo Anual")
                tabela_anual = create_annual_table(tabela_diaria)
                st.dataframe(
                    tabela_anual.style.format({
                        'Valor Bruto': "R${:.2f}",
                        'Rendimento Bruto': "R${:.2f}",
                        'IR a Pagar': "R${:.2f}",
                        'Valor Líquido': "R${:.2f}"
                    }),
                    use_container_width=True
                )

                # Exibe o valor final
                valor_final_liquido = tabela_diaria['Valor Líquido'].iloc[-1]
                valor_final_bruto = tabela_diaria['Valor Bruto'].iloc[-1]

                st.success(f"Valor Final do Investimento (Bruto): **R${valor_final_bruto:.2f}**")
                st.success(f"Valor Final do Investimento (Líquido): **R${valor_final_liquido:.2f}**")
                
            else:
                st.warning("Não foi possível gerar a tabela. Verifique os dados da API.")
        else:
            st.warning("Não foi possível obter os dados da API. Tente novamente mais tarde.")
