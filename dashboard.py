import pandas as pd
import plotly.graph_objects as go
import yahooquery as yq
import streamlit as st
from typing import Tuple

def prezzo_medio_carico(df: pd.DataFrame) -> pd.DataFrame:
    """
    Funzione per calcolare il prezzo medio di carico.

    Args:
        df: Dataframe che contiene le colonne 'Prezzo' e 'Quote'.

    Returns:
        df: Dataframe con la colonna aggiuntiva 'Prezzo medio di carico'.
    """
    df = df.copy()
    pmc = (df['Quote']*df['Prezzo']).cumsum()/df['Quote'].cumsum()
    df['Prezzo medio di carico'] = pmc
    return df

def leggi_dati_legenda(file: str) -> pd.DataFrame:
    '''
    Funzione per leggere il dataframe che contiene la legenda degli ETF.

    Args:
        file: Nome del file da leggere.

    Returns:
        df_leg: Dataframe che contiene la legenda degli ETF.
    '''
    df_leg = pd.read_excel(file, sheet_name = 'Legenda')
    return df_leg

def leggi_dati_versamenti(file: str) -> pd.DataFrame:
    '''
    Funzione per leggere il dataframe che contiene i versamenti.

    Args:
        file: Nome del file da leggere.

    Returns:
        df_vers: Dataframe che contiene i versamenti.
    '''
    df_vers = pd.read_excel(file, sheet_name = 'Versamenti')
    # controvalore
    df_vers['Controvalore'] = df_vers['Prezzo']*df_vers['Quote']
    # calcolo prezzo medio di carico
    df_vers = df_vers.groupby('ETF').apply(prezzo_medio_carico, include_groups = False).droplevel(1, axis = 0).reset_index().set_index('Data').sort_index()
    # calcolo quote cumulate
    df_temp = df_vers.groupby('ETF').apply(lambda group: group['Quote'].cumsum(), include_groups = False).reset_index().rename(columns = {'Quote': 'Quote cumulate'})
    df_vers = df_vers.merge(df_temp, on = ['Data', 'ETF'], how = 'left').set_index('Data')
    # controvalore cumulato
    df_vers['Controvalore cumulato'] = df_vers['Prezzo medio di carico']*df_vers['Quote cumulate']
    return df_vers

def pivot_versamenti(df_vers: pd.DataFrame) -> pd.DataFrame:
    '''
    Funzione per fare il pivot del dataframe dei versamenti.

    Args:
        df_vers: Dataframe che contiene i versamenti.

    Returns:
        df_vers_piv: Dataframe che contiene i versamenti in formato pivot.
    '''
    # pivot per ETF
    df_vers_piv = df_vers.reset_index().pivot(index = 'Data', columns = 'ETF', values = [col for col in df_vers.columns if col not in ['Data', 'ETF']])
    #
    df_vers_piv['Quote'] = df_vers_piv['Quote'].fillna(0).astype(int)
    df_vers_piv['Controvalore'] = df_vers_piv['Controvalore'].ffill().fillna(0)
    df_vers_piv['Prezzo medio di carico'] = df_vers_piv['Prezzo medio di carico'].ffill()
    df_vers_piv['Quote cumulate'] = df_vers_piv['Quote cumulate'].ffill().fillna(0).astype(int)
    df_vers_piv['Controvalore cumulato'] = df_vers_piv['Controvalore cumulato'].ffill().fillna(0)
    return df_vers_piv

def ottieni_dati_storici(df_leg: pd.DataFrame, df_vers_piv: pd.DataFrame) -> pd.DataFrame:
    '''
    Funzione per ottenere i dati storici degli ETF.

    Args:
        df_leg: Dataframe che contiene la legenda degli ETF.
        df_vers_piv: Dataframe che contiene i versamenti in formato pivot.

    Returns:
        df_hist: Dataframe con i dati storici degli ETF.
    '''
    # dati storici
    df_hist = []
    for ticker in df_leg['Ticker']:
        tick = yq.Ticker(ticker)
        df_temp = tick.history(period = 'max').reset_index()
        df_temp['date'] = pd.to_datetime(df_temp['date'].astype(str).str.split(' ').str[0])
        df_temp = df_temp.set_index('date')['close'].loc[df_vers_piv.index.min():]
        df_temp = pd.DataFrame(df_temp).rename(columns = {'close': df_leg.loc[df_leg['Ticker'] == ticker, 'ISIN'].values[0]})
        df_hist.append(df_temp)
    df_hist = pd.concat(df_hist, axis = 1)
    df_hist.columns = pd.MultiIndex.from_product((['Prezzo'], df_hist.columns))
    return df_hist

def calcola_rendimenti(df_vers_piv: pd.DataFrame, df_hist: pd.DataFrame):
    '''
    Funzione per fare il pivot del dataframe dei rendimenti.

    Args:
        df_vers_piv: Dataframe che contiene i versamenti in formato pivot.
        df_hist: Dataframe con i dati storici degli ETF.

    Returns:
        df_rend: Dataframe che contiene i rendimenti.
    '''
    df_rend = df_vers_piv[['Controvalore cumulato', 'Prezzo medio di carico']].copy()
    for ticker in df_rend.columns.levels[1]:
        df_rend['Peso', ticker] = df_rend['Controvalore cumulato', ticker]/df_rend['Controvalore cumulato'].sum(axis = 1)
    df_rend = df_rend.drop('Controvalore cumulato', axis = 1)
    # aggiungi prezzi storici
    df_rend = pd.concat((df_hist, df_rend), axis = 1)
    #
    df_rend['Peso'] = df_rend['Peso'].ffill()
    df_rend['Prezzo medio di carico'] = df_rend['Prezzo medio di carico'].ffill()
    # calcola rendimento
    for ticker in df_rend.columns.levels[1]:
        df_rend['Rendimento', ticker] = (df_rend['Prezzo', ticker] - df_rend['Prezzo medio di carico', ticker])/df_rend['Prezzo medio di carico', ticker]*100
    df_rend['Rendimento', 'Totale'] = (df_rend['Rendimento']*df_rend['Peso']).sum(axis = 1)
    return df_rend

def tick_plot(df_vers_piv: pd.DataFrame) -> Tuple[list, list]:
    '''
    Funzione per fare ottenere i tick per i grafici.

    Args:
        df_vers_piv: Dataframe che contiene i versamenti in formato pivot.

    Returns:
        ticks: List of ticks position.
        ticktext: List of text for ticks.
    '''
    dict_mesi = {1: 'Gen', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'Mag', 6: 'Giu', 7: 'Lug', 8: 'Ago', 9: 'Set', 10: 'Ott', 11: 'Nov', 12: 'Dic'}
    ticks = pd.date_range(df_vers_piv.index.min(), df_vers_piv.index.max(), freq = '3ME')
    ticktext = [f"{dict_mesi[d.month]} {d.year}" for d in ticks]
    return ticks, ticktext

def grafico_rendimenti(df_vers_piv: pd.DataFrame, df_rend: pd.DataFrame, ticks: list, ticktext: list) -> None:
    '''
    Funzione per fare il grafico dei rendimenti.

    Args:
        df_vers_piv: Dataframe che contiene i versamenti in formato pivot.
        df_rend: Dataframe che contiene i rendimenti.
        ticks: List of ticks position.
        ticktext: List of text for ticks.

    Returns: None.
    '''
    dict_colori = {0: 'red', 1: 'blue', 2: 'yellow', 3: 'purple', 4: 'cyan',  5: 'magenta', 6: 'orange'}
    #
    figure = go.Figure()
    figure.update_layout(go.Layout(margin = {'l': 20, 't': 20, 'r': 20, 'b': 20}, template = 'plotly_dark', legend = {'font': {'size': 14}}, width = 1000,
                                   xaxis = {'title': {'text': 'Data', 'font': {'size': 20}}, 'tickfont': {'size': 16}},
                                   yaxis = {'title': {'text': 'Rendimento portafoglio (%)', 'font': {'size': 20}}, 'tickfont': {'size': 16}}))
    for i, instr in enumerate(df_vers_piv.columns.levels[1]):
        figure.add_trace(go.Scatter(x = df_rend.index, y = df_rend['Rendimento', instr], name = instr, line_color = dict_colori[i]))
    figure.add_trace(go.Scatter(x = df_rend.index, y = df_rend['Rendimento', 'Totale'], name = 'Totale', line_color = 'lime'))
    figure.update_xaxes(tickvals = ticks, ticktext = ticktext)
    st.plotly_chart(figure)

def grafico_controvalore(df_vers_piv: pd.DataFrame, ticks: list, ticktext: list) -> None:
    '''
    Funzione per fare il grafico dei controvalori.

    Args:
        df_vers_piv: Dataframe che contiene i versamenti in formato pivot.
        ticks: List of ticks position.
        ticktext: List of text for ticks.

    Returns: None.
    '''
    dict_colori = {0: 'red', 1: 'blue', 2: 'yellow', 3: 'purple', 4: 'cyan',  5: 'magenta', 6: 'orange'}
    #
    figure = go.Figure()
    figure.update_layout(go.Layout(margin = {'l': 20, 't': 20, 'r': 20, 'b': 20}, template = 'plotly_dark', legend = {'font': {'size': 14}}, width = 1000,
                                   xaxis = {'title': {'text': 'Data', 'font': {'size': 20}}, 'tickfont': {'size': 16}},
                                   yaxis = {'title': {'text': 'Controvalore portafoglio [€]', 'font': {'size': 20}}, 'tickfont': {'size': 16}}))
    for i, instr in enumerate(df_vers_piv.columns.levels[1]):
        figure.add_trace(go.Scatter(x = df_vers_piv.index, y = df_vers_piv['Controvalore cumulato', instr], name = instr, line_color = dict_colori[i]))
    figure.add_trace(go.Scatter(x = df_vers_piv.index, y = df_vers_piv['Controvalore cumulato'].sum(axis = 1), name = 'Totale', line_color = 'lime'))
    figure.update_xaxes(tickvals = ticks, ticktext = ticktext)
    st.plotly_chart(figure)

def grafico_composizione_portf(df_vers_piv: pd.DataFrame, ticks: list, ticktext: list) -> None:
    '''
    Funzione per fare il grafico della composizione del portafoglio.

    Args:
        df_vers_piv: Dataframe che contiene i versamenti in formato pivot.
        ticks: List of ticks position.
        ticktext: List of text for ticks.

    Returns: None.
    '''
    dict_colori = {0: 'red', 1: 'blue', 2: 'yellow', 3: 'purple', 4: 'cyan',  5: 'magenta', 6: 'orange'}
    #
    figure = go.Figure()
    figure.update_layout(go.Layout(margin = {'l': 20, 't': 20, 'r': 20, 'b': 20}, template = 'plotly_dark', legend = {'font': {'size': 14}}, width = 1000,
                                   xaxis = {'title': {'text': 'Data', 'font': {'size': 20}}, 'tickfont': {'size': 16}},
                                   yaxis = {'title': {'text': 'Composizione portafoglio (%)', 'font': {'size': 20}}, 'tickfont': {'size': 16}}))
    for i, instr in enumerate(df_vers_piv.columns.levels[1]):
        figure.add_trace(go.Scatter(x = df_vers_piv.index, y = 100*df_vers_piv['Controvalore cumulato', instr]/df_vers_piv['Controvalore cumulato'].sum(axis = 1),
                                    name = instr,
                                    line_color = dict_colori[i]))
    figure.update_xaxes(tickvals = ticks, ticktext = ticktext)
    st.plotly_chart(figure)

if __name__ == '__main__':
    placeholder = st.empty()
    with placeholder.container():
        st.markdown('''
            Trascinare un foglio excel con le seguenti caratteristiche:
            - Un foglio chiamato "Versamenti" con le seguenti colonne:
                - **ETF**: contiene il codice ISIN dell'ETF;
                - **Data**: contiene la data di acquisto;
                - **Prezzo**: contiene il prezzo di acquisto;
                - **Quote**: contiene il numero di quote acquistate.
            - Un foglio chiamato "Legenda" con le seguenti colonne:
                - **ISIN**: contiene il codice ISIN dell'ETF;
                - **Ticker**: contiene il ticker dell'ETF, seguito da ".MI".
            ''')
        file = st.file_uploader('Caricare file excel')
        button = st.button('Run', disabled=file is None)
    if button == True:
        placeholder.empty()
        # st.set_page_config(layout = 'wide')
        # ottieni dati versametni
        df_leg = leggi_dati_legenda(file = file)
        df_vers = leggi_dati_versamenti(file = file)
        df_vers_piv = pivot_versamenti(df_vers = df_vers)
        # ottieni dati storici
        df_hist = ottieni_dati_storici(df_leg = df_leg, df_vers_piv = df_vers_piv)
        # calcola rendimenti
        df_rend = calcola_rendimenti(df_vers_piv = df_vers_piv, df_hist = df_hist)
        # ottieni tick per grafici
        ticks, ticktext = tick_plot(df_vers_piv = df_vers_piv)
        # produci grafici
        st.header('Rendimento del portafoglio')
        grafico_rendimenti(df_vers_piv = df_vers_piv, df_rend = df_rend, ticks = ticks, ticktext = ticktext)
        st.header('Controvalore del portafoglio')
        grafico_controvalore(df_vers_piv = df_vers_piv, ticks = ticks, ticktext = ticktext)
        st.header('Composizione del portafoglio')
        grafico_composizione_portf(df_vers_piv = df_vers_piv, ticks = ticks, ticktext = ticktext)