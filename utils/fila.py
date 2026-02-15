class FileQueue:
    def __init__(self, filename="fila.txt"):
        self.filename = filename
        # Garante que o arquivo existe
        open(self.filename, "a").close()

    def enqueue(self, item):
        """Adiciona item à fila."""
        with open(self.filename, "a", encoding="utf-8") as f:
            f.write(str(item) + "\n")

    def dequeue(self):
        """Remove e retorna o primeiro item da fila."""
        with open(self.filename, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if not lines:
            return None  # fila vazia

        first = lines[0].strip()

        # Regrava tirando o primeiro
        with open(self.filename, "w", encoding="utf-8") as f:
            f.writelines(lines[1:])

        return first

    def peek(self):
        """Lê o primeiro item sem remover."""
        with open(self.filename, "r", encoding="utf-8") as f:
            line = f.readline()
            return line.strip() if line else None

    def is_empty(self):
        """Retorna True se a fila estiver vazia."""
        return self.peek() is None
