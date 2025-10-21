import pandas as pd
from utils.utils import create_static_data, ANPVendas, ANPPrecos, create_or_get_model_run, update_model_metrics, get_best_model_run
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import math
import statsmodels.api as sm
from scipy.stats import norm

import torch

from darts.dataprocessing.transformers import Scaler
from darts.models import (
    ARIMA,
    FourTheta,
)
from darts.metrics import mape

from sklearn.preprocessing import MinMaxScaler

from classes.const import DATE_FORMAT_STRING, VAL_START, TEST_START
from classes.functions import resample_month_series_in_week_series
from classes.metrics import sle
from classes import TimeSeries
from classes.models.preprocessing import Detrend
from classes.models.window import Takens
from classes.models import (
    NARX,
    DA_RNN,
    IDLN,
    IMP,
    MLP,
    TFT,
    NHiTS,
    NLinear,
    RandomWalkModel,
)
from classes.metrics import Hurst, UTheil
from classes.functions import plot_series, plot_series_labels, plot_trend_line, eval_model, plot_correlation_matrix

import optuna

from optuna.visualization import (
    plot_optimization_history,
    plot_contour,
    plot_param_importances,
)

from pytorch_lightning.callbacks import Callback, EarlyStopping

from pyswarm import pso
import copy

# Criação do banco de dados
create_static_data()
anp_vendas = ANPVendas()
anp_precos = ANPPrecos()
# Criação do dataframe
df = pd.merge(anp_vendas.get_data(), anp_precos.get_data(), on='month', how='inner')

d_etanol_hid = TimeSeries.from_dataframe(df, "month", "Dem. Etanol H.", freq='MS')
d_gasolina_com = TimeSeries.from_dataframe(df, "month", "Dem. Gasolina C.", freq='MS')
d_gasolina_eq = TimeSeries.from_dataframe(df, "month", "Dem. Gasolina Eq.", freq='MS')
d_ciclo_otto = TimeSeries.from_dataframe(df, "month", "Dem. Ciclo Otto", freq='MS')
p_etanol_hid = TimeSeries.from_dataframe(df, "month", "Pr. Etanol H.", freq='MS')
p_gasolina_com = TimeSeries.from_dataframe(df, "month", "Pr. Gasolina C.", freq='MS')
p_r_etanol_gasolina = TimeSeries.from_dataframe(df, "month", "Pr. Etanol H. / Pr. Gasolina C.", freq='MS')
p_r_etanol_gasolina_bool = TimeSeries.from_dataframe(df, "month", "Pr. Etanol H. / Pr. Gasolina C. < 0,7", freq='MS')
p_d_etanol_gasolina = TimeSeries.from_dataframe(df, "month", "Pr. Etanol H. - Pr. Gasolina C.", freq='MS')

# Datas de início e fim da série completa
start_date = d_etanol_hid.start_time()
end_date = d_etanol_hid.end_time()

# Data final para treino+validação (dez/2024)
val_end = pd.Timestamp("2024-12-31")

# Série até dez/2024
train_val_series = d_etanol_hid.slice(start_date, val_end)

# Calcular índice de corte 70% treino / 30% validação
train_len = int(len(train_val_series) * 0.7)

# Datas correspondentes ao corte
train_start = train_val_series.start_time()
train_end = train_val_series.time_index[train_len - 1]  # último ponto do treino
VAL_START = train_end + pd.offsets.MonthBegin(1)        # mês seguinte
TEST_START = pd.Timestamp("2025-01-01")

train, val, test = d_etanol_hid.split(
    [pd.Timestamp(VAL_START), pd.Timestamp(TEST_START)]
)
train_d_gasolina, val_d_gasolina, test_d_gasolina = d_gasolina_com.split(
    [pd.Timestamp(VAL_START), pd.Timestamp(TEST_START)]
)
train_d_gasolina_eq, val_d_gasolina_eq, test_d_gasolina_eq = d_gasolina_eq.split(
    [pd.Timestamp(VAL_START), pd.Timestamp(TEST_START)]
)
train_d_ciclo_otto, val_d_ciclo_otto, test_d_ciclo_otto = d_ciclo_otto.split(
    [pd.Timestamp(VAL_START), pd.Timestamp(TEST_START)]
)
train_p_etanol, val_p_etanol, test_p_etanol = p_etanol_hid.split(
    [pd.Timestamp(VAL_START), pd.Timestamp(TEST_START)]
)
train_p_gasolina, val_p_gasolina, test_p_gasolina = p_gasolina_com.split(
    [pd.Timestamp(VAL_START), pd.Timestamp(TEST_START)]
)
train_p_r_etanol_gasolina, val_p_r_etanol_gasolina, test_p_r_etanol_gasolina = p_r_etanol_gasolina.split(
    [pd.Timestamp(VAL_START), pd.Timestamp(TEST_START)]
)
train_p_d_etanol_gasolina, val_p_d_etanol_gasolina, test_p_d_etanol_gasolina = p_d_etanol_gasolina.split(
    [pd.Timestamp(VAL_START), pd.Timestamp(TEST_START)]
)
train_p_r_etanol_gasolina_bool, val_p_r_etanol_gasolina_bool, test_p_r_etanol_gasolina_bool = p_r_etanol_gasolina_bool.split(
    [pd.Timestamp(VAL_START), pd.Timestamp(TEST_START)]
)

d_etanol_hid_filtered = d_etanol_hid.filter()[0]
d_gasolina_com_filtered = d_gasolina_com.filter()[0]
d_gasolina_eq_filtered = d_gasolina_eq.filter()[0]
d_ciclo_otto_filtered = d_ciclo_otto.filter()[0]
p_etanol_hid_filtered = p_etanol_hid.filter()[0]
p_gasolina_com_filtered = p_gasolina_com.filter()[0]
p_r_etanol_gasolina_filtered = p_r_etanol_gasolina.filter()[0]
p_r_etanol_gasolina_bool_filtered = p_r_etanol_gasolina_bool.filter()[0]
p_d_etanol_gasolina_filtered = p_d_etanol_gasolina.filter()[0]

# --- Supondo que sua classe Detrend já está definida ---
scaler = Detrend()

# --- Função auxiliar para detrend e reconstruir TimeSeries ---
def detrend_series(train, val, test, series):
    # Nome do componente original
    component_name = series.columns[0]
    
    scaler = Detrend()
    
    # Extrair numpy univariado
    train_np = train.univariate_component(0).values()[:,0]
    val_np = val.univariate_component(0).values()[:,0]
    test_np = test.univariate_component(0).values()[:,0]
    series_np = series.univariate_component(0).values()[:,0]

    # Fit e transform no treino
    train_detrend_np = scaler.fit_transform(train_np)
    val_detrend_np = scaler.transform(val_np)
    test_detrend_np = scaler.transform(test_np)
    series_detrend_np = scaler.transform(series_np)

    # Reconstruir TimeSeries mantendo time_index
    train_detrend = TimeSeries.from_times_and_values(train.time_index, train_detrend_np.reshape(-1,1), columns=[component_name])
    val_detrend = TimeSeries.from_times_and_values(val.time_index, val_detrend_np.reshape(-1,1), columns=[component_name])
    test_detrend = TimeSeries.from_times_and_values(test.time_index, test_detrend_np.reshape(-1,1), columns=[component_name])
    series_detrend = TimeSeries.from_times_and_values(series.time_index, series_detrend_np.reshape(-1,1), columns=[component_name])

    return train_detrend, val_detrend, test_detrend, series_detrend


train_detrend, val_detrend, test_detrend, d_etanol_hid_detrend = detrend_series(train, val, test, d_etanol_hid)
train_d_gasolina_detrend, val_d_gasolina_detrend, test_d_gasolina_detrend, d_gasolina_com_detrend = detrend_series(train_d_gasolina, val_d_gasolina, test_d_gasolina, d_gasolina_com)
train_d_gasolina_eq_detrend, val_d_gasolina_eq_detrend, test_d_gasolina_eq_detrend, d_gasolina_eq_detrend = detrend_series(train_d_gasolina_eq, val_d_gasolina_eq, test_d_gasolina_eq, d_gasolina_eq)
train_d_ciclo_otto_detrend, val_d_ciclo_otto_detrend, test_d_ciclo_otto_detrend, d_ciclo_otto_detrend = detrend_series(train_d_ciclo_otto, val_d_ciclo_otto, test_d_ciclo_otto, d_ciclo_otto)
train_p_etanol_detrend, val_p_etanol_detrend, test_p_etanol_detrend, p_etanol_hid_detrend = detrend_series(train_p_etanol, val_p_etanol, test_p_etanol, p_etanol_hid)
train_p_gasolina_detrend, val_p_gasolina_detrend, test_p_gasolina_detrend, p_gasolina_com_detrend = detrend_series(train_p_gasolina, val_p_gasolina, test_p_gasolina, p_gasolina_com)
train_p_r_etanol_gasolina_detrend, val_p_r_etanol_gasolina_detrend, test_p_r_etanol_gasolina_detrend, p_r_etanol_gasolina_detrend = detrend_series(train_p_r_etanol_gasolina, val_p_r_etanol_gasolina, test_p_r_etanol_gasolina, p_r_etanol_gasolina)
train_p_d_etanol_gasolina_detrend, val_p_d_etanol_gasolina_detrend, test_p_d_etanol_gasolina_detrend, p_d_etanol_gasolina_detrend = detrend_series(train_p_d_etanol_gasolina, val_p_d_etanol_gasolina, test_p_d_etanol_gasolina, p_d_etanol_gasolina)
train_p_r_etanol_gasolina_bool_detrend, val_p_r_etanol_gasolina_bool_detrend, test_p_r_etanol_gasolina_bool_detrend, p_r_etanol_gasolina_bool_detrend = detrend_series(train_p_r_etanol_gasolina_bool, val_p_r_etanol_gasolina_bool, test_p_r_etanol_gasolina_bool, p_r_etanol_gasolina_bool)

d_etanol_hid_detrend_filtered = d_etanol_hid_detrend.filter()[0]
d_gasolina_com_detrend_filtered = d_gasolina_com_detrend.filter()[0]
d_gasolina_eq_detrend_filtered = d_gasolina_eq_detrend.filter()[0]
d_ciclo_otto_detrend_filtered = d_ciclo_otto_detrend.filter()[0]
p_etanol_hid_detrend_filtered = p_etanol_hid_detrend.filter()[0]
p_gasolina_com_detrend_filtered = p_gasolina_com_detrend.filter()[0]
p_r_etanol_gasolina_detrend_filtered = p_r_etanol_gasolina_detrend.filter()[0]
p_r_etanol_gasolina_bool_detrend_filtered = p_r_etanol_gasolina_bool_detrend.filter()[0]
p_d_etanol_gasolina_detrend_filtered = p_d_etanol_gasolina_detrend.filter()[0]

model_name = 'NARX'
series_train=['train_p_gasolina_detrend_scaled', 'train_detrend_scaled']

for input_chunk_length in [6]:
    for output_chunk_length in [3]:
       for hidden_size in range(2, 10):
           for batch_size in range(2, 10):
               for lr in range(2, 7):
                    try:
                        model_run, existing = create_or_get_model_run(
                            model_name=model_name,
                            parametros={                       
                                'input_chunk_length': input_chunk_length,
                                'output_chunk_length': output_chunk_length,
                                'hidden_size': hidden_size,
                                'batch_size': batch_size,
                                'lr': lr,
                            },
                            series_train=series_train
                        )
                        if existing:
                            pass
                        model = NARX(
                            input_chunk_length=input_chunk_length,
                            output_chunk_length=output_chunk_length,
                            hidden_size=2**hidden_size,
                            batch_size=2**batch_size,
                            n_epochs=200,
                            lr=10**(-lr),
                            preprocessing = [Detrend(),MinMaxScaler()],
                            random_state = 0,
                        )
                        model.fit([train_p_gasolina, train])
                        metrics = model.evaluate(val)
                        print({
                            'mape': metrics['mape'],
                            'sle': metrics['sle'],
                            'rmse': metrics['rmse'],
                            'mse': metrics['mse'],
                            'u1': metrics['u1'],
                            'u2': metrics['u2'],
                            'lr': 10**(-lr),
                            'input_chunk_length': input_chunk_length,
                            'output_chunk_length': output_chunk_length,
                            'hidden_size': 2**hidden_size,
                            'batch_size': 2**batch_size,
                        })
                        update_model_metrics(model_run, **metrics)
                    except:
                        print('Erro')
