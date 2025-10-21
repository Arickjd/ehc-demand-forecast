import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import asc
from sqlalchemy.orm import Session
from sqlalchemy import and_
import io
from tqdm.notebook import tqdm

from database.models import engine, Fonte, Regiao, UF, Produto, Dado, ModelRun

import uuid

def create_or_get_model_run(model_name: str, parametros: dict, series_train=None):
    """
    Cria uma execução de modelo se não existir uma com o mesmo nome e parâmetros.
    Retorna a instância ModelRun.
    """
    Session = sessionmaker(bind=engine)
    session = Session()
    # Tenta encontrar execução existente
    existing = session.query(ModelRun).filter(
        and_(
            ModelRun.model_name == model_name,
            ModelRun.parametros == parametros,
            ModelRun.series_train == series_train,
        )
    ).first()

    if existing:
        return existing, True  # Já existe, retorna

    # Cria um novo run_id único
    run_id = str(uuid.uuid4())

    new_run = ModelRun(
        run_id=run_id,
        n_run=1,  # Começa com 1
        model_name=model_name,
        parametros=parametros,
        series_train=series_train
    )

    session.add(new_run)
    session.commit()
    session.refresh(new_run)
    return new_run, False


def get_best_model_run(model_name: str, series_train=None, metric="mape"):
    """
    Retorna a execução do modelo com menor valor da métrica especificada.
    """
    Session = sessionmaker(bind=engine)
    session = Session()

    query = session.query(ModelRun).filter(
        ModelRun.model_name == model_name
    )

    # Confere se a coluna existe
    column = getattr(ModelRun, metric, None)
    if column is None:
        raise ValueError(f"A métrica '{metric}' não existe na tabela ModelRun")

    if series_train is not None:
        query = query.filter(ModelRun.series_train == series_train)

    query = query.filter(column.isnot(None))

    # Ordena pela métrica crescente e pega o primeiro
    best_run = query.order_by(asc(getattr(ModelRun, metric))).first()
    session.close()
    return best_run



def update_model_metrics(model_run: ModelRun, **metrics):
    """
    Atualiza as métricas de desempenho (MAPE, MAE, etc.) para um ModelRun existente.
    """
    Session = sessionmaker(bind=engine)
    session = Session()

    # Recarrega a instância na sessão atual usando o ID
    model_run = session.get(ModelRun, model_run.id)
    if model_run is None:
        raise ValueError("ModelRun não encontrado na sessão atual.")
    
    for key, value in metrics.items():
        if hasattr(model_run, key):
            setattr(model_run, key, value)
    session.commit()
    session.refresh(model_run)
    return model_run


class FonteBehavior:
    def get_last_update(self):
        raise NotImplementedError

    def get_data(self):
        raise NotImplementedError

    def get_data_origin(self):
        raise NotImplementedError
        
    def update_database(self):
        raise NotImplementedError

    # Função para ajustar nome da UF
    @staticmethod
    def ajustar_nome_uf(nome_uf):
        return nome_uf.lower().title().replace('Do ', 'do ').replace('De ', 'de ')
    
    # Função para ajustar nome do produto
    @staticmethod
    def ajustar_nome_produto(nome_produto):
        if nome_produto == 'GASOLINA C':
            return 'Gasolina Comum'
        elif nome_produto == 'GLP':
            return 'GLP'
        elif nome_produto == 'GNV':
            return 'GNV'
        return nome_produto.title().replace('Oleo', 'Óleo')

class ANPVendas(FonteBehavior):
    NOME = "ANP - Vendas de Combustíveis"
    
    def get_last_update(self):
        url = "https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/vendas-de-derivados-de-petroleo-e-biocombustiveis"
    
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Buscar a fonte "ANP - Vendas de Combustíveis"
        fonte = session.query(Fonte).filter_by(nome="ANP - Vendas de Combustíveis").first()
        url_font = fonte.url
        session.close()
        
        try:
            response = requests.get(url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Encontrar o <a> que aponta para o link específico
            a_tag = soup.find('a', href=url_font)
            
            # Encontrar o <li> que contém esse <a>
            li_tag = a_tag.find_parent('li')
            
            # Obter a data que vem após o <a>
            date_text = li_tag.text.split("atualizado em")[1].strip()[:-1]
        except:
            return None
        # Converter para datetime
        return datetime.strptime(date_text, "%d/%m/%Y")

    def get_data_origin(self):
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Buscar a fonte "ANP - Vendas de Combustíveis"
        fonte = session.query(Fonte).filter_by(nome=self.NOME).first()
        url = fonte.url
        session.close()
        try:
            # Baixar o conteúdo do arquivo
            response = requests.get(url)
            response.encoding = "utf-8" 
            text = response.text
            
            # Corrigir linhas que começam com ';' unindo-as à linha anterior
            lines = text.split("\n")
            cleaned_lines = []
            for line in lines:
                if line.startswith(";") and cleaned_lines:
                    cleaned_lines[-1] += line  # Junta à linha anterior
                else:
                    cleaned_lines.append(line)
            
            # Criar um novo texto limpo
            cleaned_text = "\n".join(cleaned_lines)
            
            # Criar DataFrame
            df = pd.read_csv(io.StringIO(cleaned_text), sep=";", encoding="utf8", decimal=",")
            
            # Dicionário para mapear meses
            mes_map = {
                "JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
                "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12
            }
    
            # Convertendo os meses para números
            df["MÊS"] = df["MÊS"].map(mes_map)
    
            # Renomeando as colunas
            df = df.rename(columns={"ANO": "year", "MÊS": "month"})
    
            # Criando a coluna datetime
            df["month"] = pd.to_datetime(df.assign(day=1)[["year", "month", "day"]])
    
            # Remover a coluna "year"
            df.drop(columns=["year"], inplace=True)
    
            # Verificar o tipo da coluna 'month' para garantir que é datetime
            if pd.api.types.is_datetime64_any_dtype(df['month']):
                return df
            else:
                return None
            
        except Exception as e:
            return None

    def update_database(self):
        # Converter para datetime
    
        date_obj = self.get_last_update()
    
        df = self.get_data_origin()
        if type(df) == type(None):
            print("Não foi possível atualizar o banco de dados")
            return None
        # Ajeitar a coluna "month" para datetime e a coluna "VENDAS" para float
        df['month'] = pd.to_datetime(df['month'])
        df['VENDAS'] = df['VENDAS'].astype(float)
        
        # Criar a sessão para interação com o banco
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Obter a Fonte (Assumindo que a fonte já foi criada anteriormente)
        fonte = session.query(Fonte).filter_by(nome=self.NOME).first()
    
        # Verificar se a fonte existe
        if fonte:
            # Se last_updated for NULL ou menor que date_obj, continuar com a atualização
            if not fonte.last_updated or fonte.last_updated < date_obj:
                print("Atualizando fonte...")
            else:
                print("Os dados já estão atualizados.")
                return 
        else:
            print("Fonte não encontrada.")
            return
        
        # Cache para armazenar combinações UF, Produto e Fonte já verificadas
        verificados = {}
        
        # Inserir os dados no banco com base no dataframe
        for index, row in tqdm(df.iterrows(), total=len(df), desc="Inserindo dados", unit="linha"):
            # Ajustar nome da UF
            uf_nome = self.ajustar_nome_uf(row['UNIDADE DA FEDERAÇÃO'])
            
            # Procurar a UF pelo nome ajustado
            uf = session.query(UF).filter_by(nome=uf_nome).first()
            
            # Ajustar nome do produto
            produto_nome = self.ajustar_nome_produto(row['PRODUTO'])
            
            # Procurar o Produto pelo nome ajustado
            produto = session.query(Produto).filter_by(nome=produto_nome).first()
            
            # Verificar se UF e Produto foram encontrados
            if uf and produto:
                # Verificar se já foi verificado essa combinação de UF, Produto e Fonte
                chave_comb = (uf.id, produto.id, fonte.id)
                
                # Se a combinação já foi verificada, não faz a busca novamente
                if chave_comb in verificados:
                    dado_existente = verificados[chave_comb]
                else:
                    # Verificar se já existe um dado com o mesmo Produto, UF e Fonte e se a data do novo dado é mais recente
                    dado_existente = session.query(Dado).filter_by(
                        uf_id=uf.id,
                        produto_id=produto.id,
                        fonte_id=fonte.id
                    ).order_by(Dado.data.desc()).first()  # Buscar o mais recente
                    
                    # Armazenar o resultado na cache (verificados)
                    verificados[chave_comb] = dado_existente
                
                # Se não existir um dado ou se o novo dado for mais recente
                if not dado_existente or row['month'] > dado_existente.data:
                    # Criar o Dado e associar à UF, Produto e Fonte
                    dado = Dado(
                        data=row['month'],  # Utilizar a data do dataframe
                        valor=row['VENDAS'],  # Valor das vendas
                        uf=uf,  # UF associada
                        produto=produto,  # Produto associado
                        fonte=fonte  # Fonte associada
                    )
                    
                    # Adicionar o Dado na sessão
                    session.add(dado)
            else:
                print(f"UF ou Produto não encontrado para a linha {index}: {row['UNIDADE DA FEDERAÇÃO']} - {row['PRODUTO']}")
        
        # Confirmar as inserções
        session.commit()
        print("Dados inseridos com sucesso!")
        
        # Após inserir os dados, atualizar a data de 'last_updated' da Fonte
        if fonte:
            fonte.set_last_updated(date_obj)  # Atualizar a data de 'last_updated'
            session.commit()  # Salvar a alteração no banco
        
        # Fechar a sessão
        session.close()

    def get_data(self):
        # Criar a sessão para interação com o banco
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Buscar a Fonte "ANP - Vendas de Combustíveis"
        fonte_anp = session.query(Fonte).filter_by(nome=self.NOME).first()
        
        # Buscar os Produtos "Etanol Hidratado" e "Gasolina Comum"
        etanol = session.query(Produto).filter_by(nome="Etanol Hidratado").first()
        gasolina = session.query(Produto).filter_by(nome="Gasolina Comum").first()
        
        # Verificar se a fonte e os produtos existem
        if fonte_anp and etanol and gasolina:
            # Consultar os dados do banco de dados filtrando pelos Produtos e pela Fonte
            dados = (
                session.query(Dado.data, Dado.valor, Dado.produto_id)
                .filter(Dado.produto_id.in_([etanol.id, gasolina.id]), Dado.fonte_id == fonte_anp.id)
                .all()
            )
            session.close()
            
            # Criar o DataFrame a partir dos dados consultados
            df = pd.DataFrame(dados, columns=["month", "vendas", "produto_id"])
        
            # Mapear os IDs para nomes dos produtos
            produto_map = {etanol.id: "Dem. Etanol H.", gasolina.id: "Dem. Gasolina C."}
            df["produto"] = df["produto_id"].map(produto_map)
        
            # Remover a coluna produto_id
            df.drop(columns=["produto_id"], inplace=True)
        
            # Transformar para formato de colunas separadas
            df = df.pivot_table(index="month", columns="produto", values="vendas", aggfunc="sum")
        
            # Adicionar a coluna "Gasolina Equivalente" (Etanol Hidratado / 1.47)
            df["Dem. Gasolina Eq."] = df["Dem. Etanol H."] / 1.47
        
            # Adicionar a coluna "Ciclo Otto" (Gasolina Comum + Gasolina Equivalente)
            df["Dem. Ciclo Otto"] = df["Dem. Gasolina Eq."] + df["Dem. Gasolina C."]
        
            # Remover o nome automático da coluna gerado pelo pivot_table
            df.columns.name = None
        
            # Resetar o índice para manter "data" como coluna normal
            df.reset_index(inplace=True)

            # Garantir que 'month' é datetime
            df['month'] = pd.to_datetime(df['month'])
            
            # Criar um índice mensal completo do menor ao maior mês de cada df
            full_index1 = pd.date_range(df['month'].min(), df['month'].max(), freq='MS')
            
            # Reindexar cada df para incluir todos os meses e preencher faltantes
            df = df.set_index('month').reindex(full_index1).ffill().rename_axis('month').reset_index()
            
            return df

class ANPPrecos(FonteBehavior):
    NOME="ANP - Preços de Combustíveis"

    def get_last_update(self):
        url = "https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/precos-revenda-e-de-distribuicao-combustiveis/serie-historica-do-levantamento-de-precos"
    
        try:
            response = requests.get(url)
            soup = BeautifulSoup(response.content, "html.parser")
    
            # Encontrar o span que contém a data
            span = soup.select_one("span.documentModified span.value")
            if span is None:
                return None
    
            date_text = span.text.strip()  # '12/09/2025 17h58'
    
            # Converter para datetime
            return datetime.strptime(date_text, "%d/%m/%Y %Hh%M")
        
        except Exception as e:
            print("Erro ao pegar última atualização:", e)
            return None

    def get_data_origin(self):
        # Link da página
        url_pagina = "https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/precos-revenda-e-de-distribuicao-combustiveis/serie-historica-do-levantamento-de-precos"
        
        # Fazer requisição
        response = requests.get(url_pagina)
        response.encoding = "utf-8"  # garantir codificação correta
        html = response.text
        
        # Parsear com BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        
        # Procurar o bloco da série mensal
        mensal_block = soup.find("h2", string="Série histórica mensal").find_next_sibling("ul")
        
        links = {}
        
        for li in mensal_block.find_all("li", recursive=False):
            periodo = li.find("a").text.strip()  # ex: "Julho de 2001 a dezembro de 2012" ou "A partir de 2013"
            
            conteudo_div = li.find("div", class_="conteudo")
            if not conteudo_div:
                continue
        
            # Procurar o link para o Brasil
            a_brasil = conteudo_div.find("a", string="Brasil")
            if a_brasil:
                links[periodo] = a_brasil["href"]
        dfs = []  # Lista para armazenar DataFrames tratados
        
        # Mostrar os resultados
        for periodo, url in links.items():
            # Baixar o conteúdo do arquivo
            response = requests.get(url)
            df = pd.read_excel(io.BytesIO(response.content))
        
            # Verificar o tipo da coluna 'month' para garantir que é datetime
            # Encontrar a linha que contém "Mês" na primeira coluna
            linha_header = df[df.iloc[:, 0].astype(str).str.strip().str.contains("Mês", case=False)].index[0]
            
            # Cortar o DataFrame para começar nessa linha
            df = df.iloc[linha_header:].reset_index(drop=True)
            
            # Definir a primeira linha como header
            df.columns = df.iloc[0]  # linha "Mês" vira header
            df = df[1:].reset_index(drop=True)  # remove a linha que virou header
        
            # Renomeando as colunas
            df = df.rename(columns={"MÊS": "month"})
            df = df.rename(columns={"PRECO MÉDIO REVENDA": 'PREÇO MÉDIO REVENDA', "PRECO MÍNIMO REVENDA": 'PREÇO MÍNIMO REVENDA', "PRECO MÁXIMO REVENDA": 'PREÇO MÁXIMO REVENDA', "PRECO MÉDIO DISTRIBUIÇÃO": 'PREÇO MÉDIO DISTRIBUIÇÃO', "PRECO MÍNIMO DISTRIBUIÇÃO": 'PREÇO MÍNIMO DISTRIBUIÇÃO', "PRECO MÁXIMO DISTRIBUIÇÃO": 'PREÇO MÁXIMO DISTRIBUIÇÃO'})
            df['month'] = pd.to_datetime(df['month'], errors='coerce')  # converte tudo que for válido

            df['PRODUTO'] = df['PRODUTO'].astype('category')  # texto categórico
            df['UNIDADE DE MEDIDA'] = df['UNIDADE DE MEDIDA'].astype('category')  # normalmente "R$/l" ou "R$/m³"
            
            # Colunas numéricas inteiras
            df['NÚMERO DE POSTOS PESQUISADOS'] = pd.to_numeric(df['NÚMERO DE POSTOS PESQUISADOS'], errors='coerce').astype('Int64')
            
            # Colunas numéricas (float, com casas decimais)
            cols_float = [
                'PREÇO MÉDIO REVENDA',
                'DESVIO PADRÃO REVENDA',
                'PREÇO MÍNIMO REVENDA',
                'PREÇO MÁXIMO REVENDA',
                'MARGEM MÉDIA REVENDA',
                'COEF DE VARIAÇÃO REVENDA',
                'PREÇO MÉDIO DISTRIBUIÇÃO',
                'DESVIO PADRÃO DISTRIBUIÇÃO',
                'PREÇO MÍNIMO DISTRIBUIÇÃO',
                'PREÇO MÁXIMO DISTRIBUIÇÃO',
                'COEF DE VARIAÇÃO DISTRIBUIÇÃO'
            ]
            
            for col in cols_float:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
            dfs.append(df)
            
        # Concatenar todos os DataFrames
        df = pd.concat(dfs, ignore_index=True)
        
        return df

    def update_database(self):
        # Converter para datetime
    
        date_obj = self.get_last_update()
    
        df = self.get_data_origin()
        if type(df) == type(None):
            print("Não foi possível atualizar o banco de dados")
            return None
        # Ajeitar a coluna "month" para datetime e a coluna "VENDAS" para float
        df['month'] = pd.to_datetime(df['month'])
        df['NÚMERO DE POSTOS PESQUISADOS'] = df['NÚMERO DE POSTOS PESQUISADOS'].astype(int)
        df['PREÇO MÉDIO REVENDA'] = df['PREÇO MÉDIO REVENDA'].astype(float)
        df['DESVIO PADRÃO REVENDA'] = df['DESVIO PADRÃO REVENDA'].astype(float)
        df['PREÇO MÍNIMO REVENDA'] = df['PREÇO MÍNIMO REVENDA'].astype(float)
        df['PREÇO MÁXIMO REVENDA'] = df['PREÇO MÁXIMO REVENDA'].astype(float)
        df['MARGEM MÉDIA REVENDA'] = df['MARGEM MÉDIA REVENDA'].astype(float)
        df['COEF DE VARIAÇÃO REVENDA'] = df['COEF DE VARIAÇÃO REVENDA'].astype(float)
        df['PREÇO MÉDIO DISTRIBUIÇÃO'] = df['PREÇO MÉDIO DISTRIBUIÇÃO'].astype(float)
        df['DESVIO PADRÃO DISTRIBUIÇÃO'] = df['DESVIO PADRÃO DISTRIBUIÇÃO'].astype(float)
        df['PREÇO MÍNIMO DISTRIBUIÇÃO'] = df['PREÇO MÍNIMO DISTRIBUIÇÃO'].astype(float)
        df['PREÇO MÁXIMO DISTRIBUIÇÃO'] = df['PREÇO MÁXIMO DISTRIBUIÇÃO'].astype(float)
        df['COEF DE VARIAÇÃO DISTRIBUIÇÃO'] = df['COEF DE VARIAÇÃO DISTRIBUIÇÃO'].astype(float)
        
        # Criar a sessão para interação com o banco
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Obter a Fonte (Assumindo que a fonte já foi criada anteriormente)
        fonte = session.query(Fonte).filter_by(nome=self.NOME).first()
    
        # Verificar se a fonte existe
        if fonte:
            # Se last_updated for NULL ou menor que date_obj, continuar com a atualização
            if not fonte.last_updated or fonte.last_updated < date_obj:
                print("Atualizando fonte...")
            else:
                print("Os dados já estão atualizados.")
                return 
        else:
            print("Fonte não encontrada.")
            return
        
        # Cache para armazenar combinações UF, Produto e Fonte já verificadas
        verificados = {}
        
        # Inserir os dados no banco com base no dataframe
        for index, row in tqdm(df.iterrows(), total=len(df), desc="Inserindo dados", unit="linha"):
            # Ajustar nome do produto
            produto_nome = self.ajustar_nome_produto(row['PRODUTO'])
            
            # Procurar o Produto pelo nome ajustado
            produto = session.query(Produto).filter_by(nome=produto_nome).first()
            
            # Verificar se UF e Produto foram encontrados
            # Verificar se já foi verificado essa combinação de UF, Produto e Fonte
            if produto:
                chave_comb = (produto.id, fonte.id)
                
                # Se a combinação já foi verificada, não faz a busca novamente
                if chave_comb in verificados:
                    dado_existente = verificados[chave_comb]
                else:
                    # Verificar se já existe um dado com o mesmo Produto, UF e Fonte e se a data do novo dado é mais recente
                    dado_existente = session.query(Dado).filter_by(
                        produto_id=produto.id,
                        fonte_id=fonte.id
                    ).order_by(Dado.data.desc()).first()  # Buscar o mais recente
                    
                    # Armazenar o resultado na cache (verificados)
                    verificados[chave_comb] = dado_existente
                
                # Se não existir um dado ou se o novo dado for mais recente
                if not dado_existente or row['month'] > dado_existente.data:
                    # Criar o Dado e associar à UF, Produto e Fonte
                    dado = Dado(
                        data=row['month'],  # Utilizar a data do dataframe
                        valor=row['PREÇO MÉDIO REVENDA'],  # Valor das vendas
                        produto=produto,  # Produto associado
                        fonte=fonte  # Fonte associada
                    )
                    
                    # Adicionar o Dado na sessão
                    session.add(dado)
            else:
                print(f"Produto não encontrado para a linha {index}: {row['PRODUTO']}")
        
        # Confirmar as inserções
        session.commit()
        print("Dados inseridos com sucesso!")
        
        # Após inserir os dados, atualizar a data de 'last_updated' da Fonte
        if fonte:
            fonte.set_last_updated(date_obj)  # Atualizar a data de 'last_updated'
            session.commit()  # Salvar a alteração no banco
        
        # Fechar a sessão
        session.close()

    def get_data(self):
        # Criar a sessão para interação com o banco
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Buscar a Fonte "ANP - Vendas de Combustíveis"
        fonte_anp = session.query(Fonte).filter_by(nome=self.NOME).first()
        
        # Buscar os Produtos "Etanol Hidratado" e "Gasolina Comum"
        etanol = session.query(Produto).filter_by(nome="Etanol Hidratado").first()
        gasolina = session.query(Produto).filter_by(nome="Gasolina Comum").first()
        
        # Verificar se a fonte e os produtos existem
        if fonte_anp and etanol and gasolina:
            # Consultar os dados do banco de dados filtrando pelos Produtos e pela Fonte
            dados = (
                session.query(Dado.data, Dado.valor, Dado.produto_id)
                .filter(Dado.produto_id.in_([etanol.id, gasolina.id]), Dado.fonte_id == fonte_anp.id)
                .all()
            )
            session.close()
            
            # Criar o DataFrame a partir dos dados consultados
            df = pd.DataFrame(dados, columns=["month", "preço", "produto_id"])
        
            # Mapear os IDs para nomes dos produtos
            produto_map = {etanol.id: "Pr. Etanol H.", gasolina.id: "Pr. Gasolina C."}
            df["produto"] = df["produto_id"].map(produto_map)
        
            # Remover a coluna produto_id
            df.drop(columns=["produto_id"], inplace=True)
        
            # Transformar para formato de colunas separadas
            df = df.pivot_table(index="month", columns="produto", values="preço", aggfunc="sum")

            # 1️⃣ Diferença: Etanol - Gasolina
            df["Pr. Etanol H. - Pr. Gasolina C."] = df["Pr. Etanol H."] - df["Pr. Gasolina C."]
            
            # 2️⃣ Razão: Etanol / Gasolina
            df["Pr. Etanol H. / Pr. Gasolina C."] = df["Pr. Etanol H."] / df["Pr. Gasolina C."]
            
            # 3️⃣ Indicador booleano: Etanol / Gasolina < 0,7
            df["Pr. Etanol H. / Pr. Gasolina C. < 0,7"] = df["Pr. Etanol H. / Pr. Gasolina C."] < 0.7
                    
            # Remover o nome automático da coluna gerado pelo pivot_table
            df.columns.name = None
        
            # Resetar o índice para manter "data" como coluna normal
            df.reset_index(inplace=True)
            # Garantir que 'month' é datetime
            df['month'] = pd.to_datetime(df['month'])
            
            # Criar um índice mensal completo do menor ao maior mês de cada df
            full_index1 = pd.date_range(df['month'].min(), df['month'].max(), freq='MS')
            
            # Reindexar cada df para incluir todos os meses e preencher faltantes
            df = df.set_index('month').reindex(full_index1).ffill().rename_axis('month').reset_index()
            
            return df


def create_static_data():
    # Criar a sessão
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Criar a Fonte com created_at e last_updated personalizados
        fonte1 = Fonte(
            nome="ANP - Vendas de Combustíveis", 
            url="https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/arquivos/vdpb/vendas-derivados-petroleo-e-etanol/vendas-combustiveis-m3-1990-2025.csv",
            created_at=None,  # Exemplo de data de criação
        )
        fonte2 = Fonte(
            nome="ANP - Preços de Combustíveis", 
            url="https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/precos-revenda-e-de-distribuicao-combustiveis/serie-historica-do-levantamento-de-precos",
            created_at=None,  # Exemplo de data de criação
        )
        
        # Inserir a fonte no banco
        session.add(fonte1)
        session.add(fonte2)
        session.commit()
    except:
        pass

    try:
        # Inserindo Regiões
        nordeste = Regiao(nome="Nordeste")
        norte = Regiao(nome="Norte")
        sul = Regiao(nome="Sul")
        sudeste = Regiao(nome="Sudeste")
        centro_oeste = Regiao(nome="Centro-Oeste")
    
        # Inserir Regiões no banco
        session.add_all([nordeste, norte, sul, sudeste, centro_oeste])
        session.commit()
    except:
        pass

    try:
        # Inserir UFs associadas às Regiões
        ufs = [
            # Nordeste
            UF(nome="Ceará", sigla="CE", regiao=nordeste),
            UF(nome="Maranhão", sigla="MA", regiao=nordeste),
            UF(nome="Pernambuco", sigla="PE", regiao=nordeste),
            UF(nome="Bahia", sigla="BA", regiao=nordeste),
            UF(nome="Paraíba", sigla="PB", regiao=nordeste),
            UF(nome="Rio Grande do Norte", sigla="RN", regiao=nordeste),
            UF(nome="Alagoas", sigla="AL", regiao=nordeste),
            UF(nome="Sergipe", sigla="SE", regiao=nordeste),
            UF(nome="Piauí", sigla="PI", regiao=nordeste),
            
            # Norte
            UF(nome="Acre", sigla="AC", regiao=norte),
            UF(nome="Amapá", sigla="AP", regiao=norte),
            UF(nome="Amazonas", sigla="AM", regiao=norte),
            UF(nome="Pará", sigla="PA", regiao=norte),
            UF(nome="Rondônia", sigla="RO", regiao=norte),
            UF(nome="Roraima", sigla="RR", regiao=norte),
            UF(nome="Tocantins", sigla="TO", regiao=norte),
            
            # Sul
            UF(nome="Paraná", sigla="PR", regiao=sul),
            UF(nome="Rio Grande do Sul", sigla="RS", regiao=sul),
            UF(nome="Santa Catarina", sigla="SC", regiao=sul),
            
            # Sudeste
            UF(nome="Espírito Santo", sigla="ES", regiao=sudeste),
            UF(nome="Minas Gerais", sigla="MG", regiao=sudeste),
            UF(nome="Rio de Janeiro", sigla="RJ", regiao=sudeste),
            UF(nome="São Paulo", sigla="SP", regiao=sudeste),
            
            # Centro-Oeste
            UF(nome="Goiás", sigla="GO", regiao=centro_oeste),
            UF(nome="Mato Grosso", sigla="MT", regiao=centro_oeste),
            UF(nome="Mato Grosso do Sul", sigla="MS", regiao=centro_oeste),
            UF(nome="Distrito Federal", sigla="DF", regiao=centro_oeste),
        ]
        
        # Inserir todas as UFs no banco
        session.add_all(ufs)
        session.commit()
    except:
        pass

    try:
        # Criando a lista de produtos com a primeira letra de cada palavra maiúscula
        produtos = [
            "ETANOL HIDRATADO",
            "GASOLINA COMUM",
            "GASOLINA DE AVIAÇÃO",
            "GASOLINA ADITIVADA",
            "GLP",
            "GNV",
            "QUEROSENE DE AVIAÇÃO",
            "QUEROSENE ILUMINANTE",
            "ÓLEO COMBUSTÍVEL",
            "ÓLEO DIESEL",
            "ÓLEO DIESEL S10"
        ]
        
        # Transformando a primeira letra de cada palavra em maiúscula
        produtos = [(produto.lower().title() if produto != 'GLP' and produto != 'GNV' else produto) for produto in produtos]
        
        # Inserindo os produtos na base de dados
        produtos_obj = [Produto(nome=produto) for produto in produtos]
        
        # Inserir os produtos no banco
        session.add_all(produtos_obj)
        session.commit()
    except:
        pass

    session.close()