"""
Bootstrap automático do JupyterLab para o projeto ehc-demand-forecast.

Uso no notebook (primeira célula):

    %run scripts/bootstrap.py

ou simplesmente:

    import sys; sys.path.insert(0, "..")

O que este script faz:
  1. Carrega o .env da raiz do projeto (via python-dotenv)
  2. Garante que a raiz do projeto esteja no sys.path
     (necessário para `import utils`, `import database` e `import classes`)
  3. Aplica a semente global definida em RANDOM_SEED
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 1) sys.path: raiz do projeto (para utils / database / classes)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 2) Carrega o .env
try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
    print(f"[bootstrap] .env carregado de {PROJECT_ROOT / '.env'}")
except ImportError:
    print("[bootstrap] python-dotenv não instalado; .env não carregado.")

# 3) Semente global
seed = os.getenv("RANDOM_SEED")
if seed:
    try:
        import random

        import numpy as np
        import torch

        random.seed(int(seed))
        np.random.seed(int(seed))
        torch.manual_seed(int(seed))
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(int(seed))
        print(f"[bootstrap] RANDOM_SEED={seed} aplicado.")
    except Exception:
        pass

print(f"[bootstrap] PROJECT_ROOT={PROJECT_ROOT}")
print(f"[bootstrap] DATABASE_URL={os.getenv('DATABASE_URL')}")
