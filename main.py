from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
from typing import Optional, List

import os

# Trova la cartella esatta in cui si trova questo script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Crea un percorso assoluto e univoco per il file SQLite
DB_NAME = os.path.join(BASE_DIR, "vocaboli_salvati.db")

# Inizializziamo l'applicazione FastAPI
app = FastAPI(
    title="Vocaboli API per Agenti IA",
    description="API REST per la gestione di vocaboli e traduzioni"
)

DB_NAME = "vocaboli_salvati.db"

# --- FUNZIONE PER INIZIALIZZARE IL DB ---
def init_db():
    """Crea la tabella vocaboli se non esiste ancora per evitare crash."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vocaboli (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parola TEXT NOT NULL,
            traduzione TEXT,
            data_salvataggio TEXT,
            imparata INTEGER DEFAULT 0,
            streak INTEGER DEFAULT 0,
            UNIQUE(parola)
        )
    """)
    conn.commit()
    conn.close()

# Eseguiamo la creazione della tabella all'avvio del server
init_db()

# --- SCHEMI DATI (Pydantic) ---
# Definiamo la struttura esatta dei dati in entrata e uscita (JSON Validation)
class VocaboloCreate(BaseModel):
    parola: str
    traduzione: Optional[str] = None

class VocaboloResponse(BaseModel):
    id: int
    parola: str
    traduzione: Optional[str]
    streak: int
    imparata: int


# --- ENDPOINT 1: READ (GET) ---
@app.get("/vocaboli", response_model=List[VocaboloResponse])
def leggi_vocaboli():
    """Restituisce la lista di tutti i vocaboli presenti nel database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, parola, traduzione, streak, imparata FROM vocaboli")
    righe = cursor.fetchall()
    conn.close()
    
    # Trasformiamo i dati del DB in una lista di dizionari/JSON
    risultato = []
    for r in righe:
        risultato.append({
            "id": r[0],
            "parola": r[1],
            "traduzione": r[2],
            "streak": r[3],
            "imparata": r[4]
        })
    return risultato


# --- ENDPOINT 2: CREATE (POST) ---
@app.post("/vocaboli", response_model=dict, status_code=201)
def crea_vocabolo(item: VocaboloCreate):
    """Riceve un oggetto JSON con parola e traduzione e lo salva nel database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO vocaboli (parola, traduzione, data_salvataggio)
            VALUES (?, ?, '2026-09-23')
        """, (item.parola.lower().strip(), item.traduzione))
        conn.commit()
        
        return {
            "status": "successo",
            "messaggio": f"Parola '{item.parola}' salvata correttamente!"
        }
    except sqlite3.IntegrityError:
        conn.close()
        # Se la parola esiste già, restituiamo un errore HTTP 400 Bad Request
        raise HTTPException(status_code=400, detail="La parola esiste già nel database.")
    finally:
        conn.close()