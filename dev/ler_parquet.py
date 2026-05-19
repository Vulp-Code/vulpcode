import pandas as pd

# Exemplo de leitura de arquivo Parquet
def ler_arquivo_parquet(caminho_arquivo):
    """
    Lê um arquivo Parquet e retorna um DataFrame pandas.

    Args:
        caminho_arquivo (str): Caminho para o arquivo .parquet

    Returns:
        pd.DataFrame: DataFrame com os dados do arquivo
    """
    try:
        df = pd.read_parquet(caminho_arquivo)
        print(f"Arquivo carregado com sucesso!")
        print(f"Shape: {df.shape}")
        print(f"\nPrimeiras linhas:")
        print(df.head())
        return df
    except FileNotFoundError:
        print(f"Erro: Arquivo '{caminho_arquivo}' não encontrado.")
        return None
    except Exception as e:
        print(f"Erro ao ler arquivo: {e}")
        return None


if __name__ == "__main__":
    # Exemplo de uso
    caminho = "exemplo.parquet"  # Substitua pelo caminho do seu arquivo
    df = ler_arquivo_parquet(caminho)

    # Informações adicionais do DataFrame
    if df is not None:
        print(f"\nColunas: {df.columns.tolist()}")
        print(f"\nInfo do DataFrame:")
        df.info()
