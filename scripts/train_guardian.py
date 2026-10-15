"""
Entrena el modelo guardián (detector de datos personales) con datos
sintéticos y lo guarda en models/guardian_ner/.

Uso:
    python -m scripts.train_guardian
"""
from guardian.training.train import train

if __name__ == "__main__":
    train()
