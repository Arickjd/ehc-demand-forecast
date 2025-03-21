import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from tqdm.notebook import tqdm

from database.models import engine, Fonte, Regiao, UF, Produto, Dado

def get_last_update_data_origin_ANP():
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

def get_data_origin_ANP():
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Buscar a fonte "ANP - Vendas de Combustíveis"
    fonte = session.query(Fonte).filter_by(nome="ANP - Vendas de Combustíveis").first()
    url = fonte.url
    session.close()
    try:
        # Ler o CSV diretamente da web
        df = pd.read_csv(url, sep=";", encoding="utf8", decimal=",")
        
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

def create_static_data():
    # Criar a sessão
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Criar a Fonte com created_at e last_updated personalizados
        fonte = Fonte(
            nome="ANP - Vendas de Combustíveis", 
            url="https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/arquivos/vdpb/vendas-derivados-petroleo-e-etanol/vendas-combustiveis-m3-1990-2025.csv",
            created_at=None,  # Exemplo de data de criação
        )
        
        # Inserir a fonte no banco
        session.add(fonte)
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
            "GLP",
            "QUEROSENE DE AVIAÇÃO",
            "QUEROSENE ILUMINANTE",
            "ÓLEO COMBUSTÍVEL",
            "ÓLEO DIESEL"
        ]
        
        # Transformando a primeira letra de cada palavra em maiúscula
        produtos = [(produto.lower().title() if produto != 'GLP' else produto) for produto in produtos]
        
        # Inserindo os produtos na base de dados
        produtos_obj = [Produto(nome=produto) for produto in produtos]
        
        # Inserir os produtos no banco
        session.add_all(produtos_obj)
        session.commit()
    except:
        pass

    session.close()

def update_database_ANP():
    # Converter para datetime
    date_obj = get_last_update_data_origin_ANP()

    df = get_data_origin_ANP()
    if type(df) == type(None):
        print("Não foi possível atualizar o banco de dados")
        return None
    # Ajeitar a coluna "month" para datetime e a coluna "VENDAS" para float
    df['month'] = pd.to_datetime(df['month'])
    df['VENDAS'] = df['VENDAS'].astype(float)
    
    # Criar a sessão para interação com o banco
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Função para ajustar nome da UF
    def ajustar_nome_uf(nome_uf):
        return nome_uf.lower().title().replace('Do ', 'do ').replace('De ', 'de ')
    
    # Função para ajustar nome do produto
    def ajustar_nome_produto(nome_produto):
        if nome_produto == 'GASOLINA C':
            return 'Gasolina Comum'
        elif nome_produto == 'GLP':
            return 'GLP'
        return nome_produto.title()
    
    # Obter a Fonte (Assumindo que a fonte já foi criada anteriormente)
    fonte = session.query(Fonte).filter_by(nome="ANP - Vendas de Combustíveis").first()

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
        uf_nome = ajustar_nome_uf(row['UNIDADE DA FEDERAÇÃO'])
        
        # Procurar a UF pelo nome ajustado
        uf = session.query(UF).filter_by(nome=uf_nome).first()
        
        # Ajustar nome do produto
        produto_nome = ajustar_nome_produto(row['PRODUTO'])
        
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

def get_dataframe_anp():
    # Criar a sessão para interação com o banco
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Buscar a Fonte "ANP - Vendas de Combustíveis"
    fonte_anp = session.query(Fonte).filter_by(nome="ANP - Vendas de Combustíveis").first()
    
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
    
        # Adicionar a coluna "Gasolina Equivalente" (Etanol Hidratado * 0.7)
        df["Dem. Gasolina Eq."] = df["Dem. Etanol H."] * 0.7
    
        # Adicionar a coluna "Ciclo Otto" (Gasolina Comum + Gasolina Equivalente)
        df["Dem. Ciclo Otto"] = df["Dem. Gasolina Eq."] + df["Dem. Gasolina C."]
    
        # Remover o nome automático da coluna gerado pelo pivot_table
        df.columns.name = None
    
        # Resetar o índice para manter "data" como coluna normal
        df.reset_index(inplace=True)
        return df