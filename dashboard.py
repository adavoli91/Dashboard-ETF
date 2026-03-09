import pandas as pd
import plotly.graph_objects as go
import yahooquery as yq
import streamlit as st
from typing import Tuple

class DashboardPAC:
    def __init__(self) -> None:
        '''
        Classe per implementare la dashboard relativa ad un PAC.

        Args: None.

        Returns: None.
        '''
        pass

    def prezzo_medio_carico(self, df: pd.DataFrame) -> pd.DataFrame:
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
        #
        return df

    def leggi_dati_legenda(self) -> None:
        '''
        Funzione per leggere il dataframe che contiene la legenda degli ETF.

        Args: None.

        Returns: None.
        '''
        self.df_leg = pd.read_excel(self.file, sheet_name = 'Legenda')

    def leggi_dati_versamenti(self) -> None:
        '''
        Funzione per leggere il dataframe che contiene i versamenti.

        Args: None.

        Returns: None.
        '''
        df_vers = pd.read_excel(self.file, sheet_name = 'Versamenti')
        # controvalore
        df_vers['Controvalore'] = df_vers['Prezzo']*df_vers['Quote']
        # calcolo prezzo medio di carico
        df_vers = df_vers.groupby('ETF').apply(self.prezzo_medio_carico, include_groups = False).droplevel(1, axis = 0).reset_index().set_index('Data').sort_index()
        # calcolo quote cumulate
        df_temp = df_vers.groupby('ETF').apply(lambda group: group['Quote'].cumsum(), include_groups = False).reset_index().rename(columns = {'Quote': 'Quote cumulate'})
        df_vers = df_vers.merge(df_temp, on = ['Data', 'ETF'], how = 'left').set_index('Data')
        # controvalore cumulato
        df_vers['Controvalore cumulato'] = df_vers['Prezzo medio di carico']*df_vers['Quote cumulate']
        #
        self.df_vers = df_vers

    def pivot_versamenti(self) -> None:
        '''
        Funzione per fare il pivot del dataframe dei versamenti.

        Args: None.

        Returns: None.
        '''
        df_vers = self.df_vers.copy()
        # pivot per ETF
        df_vers_piv = df_vers.reset_index().pivot(index = 'Data', columns = 'ETF', values = [col for col in df_vers.columns if col not in ['Data', 'ETF']])
        #
        df_vers_piv['Quote'] = df_vers_piv['Quote'].fillna(0).astype(int)
        df_vers_piv['Controvalore'] = df_vers_piv['Controvalore'].ffill().fillna(0)
        df_vers_piv['Prezzo medio di carico'] = df_vers_piv['Prezzo medio di carico'].ffill()
        df_vers_piv['Quote cumulate'] = df_vers_piv['Quote cumulate'].ffill().fillna(0).astype(int)
        df_vers_piv['Controvalore cumulato'] = df_vers_piv['Controvalore cumulato'].ffill().fillna(0)
        self.df_vers_piv = df_vers_piv

    def ottieni_dati_storici(self) -> None:
        '''
        Funzione per ottenere i dati storici degli ETF.

        Args: None.

        Returns: None.
        '''
        df_leg = self.df_leg.copy()
        df_vers_piv = self.df_vers_piv.copy()
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
        #
        self.df_hist = df_hist

    def calcola_rendimenti(self) -> None:
        '''
        Funzione per fare il pivot del dataframe dei rendimenti.

        Args: None.

        Returns: None.
        '''
        df_vers_piv = self.df_vers_piv.copy()
        df_hist = self.df_hist.copy()
        #
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
        #
        self.df_rend = df_rend

    def tick_plot(self) -> None:
        '''
        Funzione per fare ottenere i tick per i grafici.

        Args: None.

        Returns: None.
        '''
        df_vers_piv = self.df_vers_piv.copy()
        #
        dict_mesi = {1: 'Gen', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'Mag', 6: 'Giu', 7: 'Lug', 8: 'Ago', 9: 'Set', 10: 'Ott', 11: 'Nov', 12: 'Dic'}
        ticks = pd.date_range(df_vers_piv.index.min(), df_vers_piv.index.max(), freq = '3ME')
        ticktext = [f"{dict_mesi[d.month]} {d.year}" for d in ticks]
        #
        self.ticks = ticks
        self.ticktext = ticktext

    def grafico_rendimenti(self) -> None:
        '''
        Funzione per fare il grafico dei rendimenti.

        Args: None.

        Returns: None.
        '''
        df_vers_piv = self.df_vers_piv.copy()
        df_rend = self.df_rend.copy()
        ticks = self.ticks.copy()
        ticktext = self.ticktext.copy()
        #
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

    def grafico_controvalore(self) -> None:
        '''
        Funzione per fare il grafico dei controvalori.

        Args: None.

        Returns: None.
        '''
        df_vers_piv = self.df_vers_piv.copy()
        ticks = self.ticks.copy()
        ticktext = self.ticktext.copy()
        #
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

    def grafico_composizione_portf(self) -> None:
        '''
        Funzione per fare il grafico della composizione del portafoglio.

        Args: None.

        Returns: None.
        '''
        df_vers_piv = self.df_vers_piv.copy()
        ticks = self.ticks.copy()
        ticktext = self.ticktext.copy()
        #
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
    
    def main(self) -> None:
        '''
        Funzione per costruire la dashboard relativa al PAC.

        Args: None.

        Returns: None.
        '''
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
            button = st.button('Run', disabled = file is None)
        if button == True:
            placeholder.empty()
            #
            self.file = file
            # ottieni dati versametni
            self.leggi_dati_legenda()
            self.leggi_dati_versamenti()
            self.pivot_versamenti()
            # ottieni dati storici
            self.ottieni_dati_storici()
            # calcola rendimenti
            self.calcola_rendimenti()
            # ottieni tick per grafici
            self.tick_plot()
            # produci grafici
            st.header('Rendimento del portafoglio')
            self.grafico_rendimenti()
            st.header('Controvalore del portafoglio')
            self.grafico_controvalore()
            st.header('Composizione del portafoglio')
            self.grafico_composizione_portf()

if __name__ == '__main__':
    st.set_page_config(layout = 'wide')
    #
    analisi = st.radio(label = 'Tipo di analisi', options = ['PAC', 'Lazy portfolio'], index = None)
    #
    if analisi == 'PAC':
        DashboardPAC().main()