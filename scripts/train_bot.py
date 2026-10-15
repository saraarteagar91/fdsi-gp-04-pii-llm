"""
Entrena el asistente Andi (clasificador de intenciones) y guarda el
modelo en models/intent_classifier.joblib junto con su reporte.

Uso:
    python -m scripts.train_bot
"""
from chatbot.training import train

if __name__ == "__main__":
    train(verbose=True)
