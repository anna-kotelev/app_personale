import streamlit as st
import pandas as pd
import sqlite3
from datetime import date
from google import genai
import os # Fornisce funzioni per interagire con il sistema operativo sottostante
from gtts import gTTS

# --- CONFIGURAZIONE DATABASE ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) # il percorso assoluto della cartella che contiene lo script in esecuzione
DB_NAME = os.path.join(BASE_DIR, "vocaboli_salvati.db")

def init_db():
    """Crea la tabella per i vocaboli con i campi per il quiz, lo streak e lo stato."""
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
    # Tabella per salvare il record in modo persistente
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            chiave TEXT PRIMARY KEY,
            valore INTEGER
        )
    """)
    # Inizializza il record a 0 se non esiste
    cursor.execute("""
        INSERT OR IGNORE INTO config (chiave, valore) VALUES ('record_punteggio', 0)
    """)
    conn.commit()
    conn.close()

init_db()

def salva_parola(parola, traduzione=None):
    """Salva la parola nel database SQLite (accetta anche traduzione vuota/None)."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    oggi = date.today().strftime("%Y-%m-%d")
    trad_val = traduzione.strip() if traduzione else None
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO vocaboli (parola, traduzione, data_salvataggio)
            VALUES (?, ?, ?)
        """, (parola.lower().strip(), trad_val, oggi))
        conn.commit()
    except Exception as e:
        st.error(f"Errore nel salvataggio: {e}")
    finally:
        conn.close()


def salva_parola(parola, traduzione=None):
    """Salva la parola nel database SQLite. Se la traduzione manca, la chiede a Gemini."""
    trad_val = traduzione.strip() if traduzione and isinstance(traduzione, str) else None
    
    # Se la traduzione manca, chiediamo a Gemini di generarla
    if not trad_val:
        try:
            client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
            prompt_trad = (
                f"Fornisci la traduzione italiana più comune, diretta e concisa della parola inglese '{parola}'. "
                f"Rispondi ESATTAMENTE e unicamente con la parola o la breve espressione tradotta in italiano, senza aggiungere altro testo, punteggiatura extra o spiegazioni."
            )
            response = client.models.generate_content(
                model="gemini-3.5-flash", 
                contents=prompt_trad,
            )
            testo_ia = str(response.text) if response.text is not None else ""
            trad_val = testo_ia.strip()
        except Exception:
            trad_val = "Da tradurre"  # Corretto: aggiunto il commento con il cancelletto

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    oggi = date.today().strftime("%Y-%m-%d")
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO vocaboli (parola, traduzione, data_salvataggio)
            VALUES (?, ?, ?)
        """, (parola.lower().strip(), trad_val, oggi))
        conn.commit()
    except Exception as e:
        st.error(f"Errore nel salvataggio: {e}")
    finally:
        conn.close()
        
def process_text_input(testo):
    """Analizza il testo inserito (formato 'parola = traduzione' oppure lista di parole separate da virgola)."""
    righe = testo.split("\n")
    conteggio = 0
    for riga in righe:
        if not riga.strip():
            continue
        # Se la riga contiene il segno '=', gestiamo coppie multiple separate da virgola o newline
        coppie = riga.split(",")
        for coppia in coppie:
            if "=" in coppia:
                parti = coppia.split("=")
                if len(parti) == 2:
                    p = parti[0].strip()
                    t = parti[1].strip()
                    if p:
                        salva_parola(p, t if t else None)
                        conteggio += 1
            else:
                # Se non c'è '=', consideriamo ogni elemento separato da virgola come sola parola inglese
                p = coppia.strip()
                if p:
                    salva_parola(p, None)
                    conteggio += 1
    return conteggio
# L'ESTENSIONE CHROME-------------------------------------------------
parametri_url = st.query_params
if "nuova_parola" in parametri_url:
    parola_ricevuta = parametri_url["nuova_parola"]
    
    if parola_ricevuta:
        tot_salvati = process_text_input(parola_ricevuta)
        if tot_salvati > 0:
            st.success(f"✨ Parola ricevuta dall'estensione e salvata con successo: '{parola_ricevuta}'")
        else:
            st.warning(f"⚠️ Ricevuto dall'estensione ma non valido: '{parola_ricevuta}'")
            
    # Pulisce i parametri dell'URL
    st.query_params.clear()

# --- INTERFACCIA STREAMLIT -------------------------------------------
st.set_page_config(page_title="Language Quiz App", page_icon="📚", layout="wide")

st.title("Language Vocabulary & Quiz App")
st.sidebar.markdown("### 🧭 Menu Principale")
pagina_selezionata = st.sidebar.radio(
    "Scegli sezione:", 
    ["🎯 Quiz", "📥 Inserisci Parole", "📊 Visualizza Database"]
)
# --- PULSANTE RESET DATABASE NELLA SIDEBAR ---
st.sidebar.markdown("---")
st.sidebar.markdown("### ⚠️ Area Pericolosa")

# Inizializziamo lo stato di conferma se non esiste
if "conferma_reset" not in st.session_state:
    st.session_state.conferma_reset = False

# Se non è ancora stato premuto il primo pulsante
if not st.session_state.conferma_reset:
    if st.sidebar.button("🗑️ Cancella Intero Dataset"):
        st.session_state.conferma_reset = True
        st.rerun()
else:
    # Se ha già cliccato, mostra il messaggio di avviso e i pulsanti di scelta
    st.sidebar.warning("Sei sicuro di voler eliminare TUTTI i vocaboli salvati?")
    col_si, col_no = st.sidebar.columns(2)
    
    with col_si:
        if st.button("Sì, cancella"):
            try:
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                # Elimina tutti i record dalla tabella vocaboli
                cursor.execute("DELETE FROM vocaboli")
                conn.commit()
                conn.close()
                st.sidebar.success("Database svuotato con successo!")
            except Exception as e:
                st.sidebar.error(f"Errore: {e}")
            
            # Reset dello stato e ricarica
            st.session_state.conferma_reset = False
            st.rerun()
            
    with col_no:
        if st.button("No"):
            st.session_state.conferma_reset = False
            st.rerun()

# ==========================================
# SEZIONE 1: MODULO QUIZ
# ==========================================
if pagina_selezionata == "🎯 Quiz":
    st.title("🎯 Modulo Quiz: Allenati con i tuoi Vocaboli")
    st.write("Metti alla prova le tue conoscenze con l'assistenza intelligente di Gemini!")

    if st.button("🚀 Avvia / Ricarica Quiz"):
        conn = sqlite3.connect(DB_NAME)
        query = "SELECT id, parola, traduzione, streak FROM vocaboli WHERE imparata = 0 ORDER BY RANDOM() LIMIT 10"
        df_quiz = pd.read_sql_query(query, conn)
        conn.close()
        
        if not df_quiz.empty:
            st.session_state.quiz_data = df_quiz.to_dict('records')
            st.session_state.quiz_index = 0
            st.session_state.punteggio_sessione = 0
            st.rerun()
        else:
            st.warning("⚠️ Non ci sono parole disponibili o hai già imparato tutto! Aggiungi nuovi vocaboli dalla sezione di inserimento.")

    # Gestione dello svolgimento del quiz
    if 'quiz_data' in st.session_state and st.session_state.quiz_data:
        idx = st.session_state.quiz_index
        
        if idx < len(st.session_state.quiz_data):
            parola_corrente = st.session_state.quiz_data[idx]
            
            # Mostriamo a schermo Punteggio e Record
            conn_rec = sqlite3.connect(DB_NAME)
            cursor_rec = conn_rec.cursor()
            cursor_rec.execute("SELECT valore FROM config WHERE chiave = 'record_punteggio'")
            res_rec = cursor_rec.fetchone()
            record_attuale = res_rec[0] if res_rec else 0
            conn_rec.close()

            st.write(f"**Punteggio attuale:** {st.session_state.punteggio_sessione} punti | 🏆 **RECORD:** {record_attuale} punti")
            # ---------------------------------------------
            
            st.write(f"Domanda {idx + 1} di {len(st.session_state.quiz_data)}")
            st.info(f"Traduci in italiano la parola inglese: **{parola_corrente['parola']}**")
            # Lettura Audio gTTS
            try:
                tts = gTTS(text=parola_corrente['parola'], lang='en')
                audio_path = "temp_quiz_audio.mp3"
                tts.save(audio_path)
                st.audio(audio_path, format='audio/mp3')
            except Exception:
                pass
            
            risposta_utente = st.text_input("La tua risposta:", key=f"risposta_{idx}")
            
            if st.button("Conferma Risposta"):
                if not risposta_utente.strip():
                    st.warning("Per favore, inserisci una risposta prima di confermare!")
                else:
                    traduzione_esistente = parola_corrente.get('traduzione')
                    if not isinstance(traduzione_esistente, str):
                        traduzione_esistente = ""
                    
                    ###
                    # Verifichiamo se abbiamo una traduzione vera e propria nel DB
                    # Controlliamo che esista, che non sia vuota e che NON sia "da tradurre"
                    trad_pulita_db = traduzione_esistente.strip().lower() if traduzione_esistente else ""
                    ha_trad_db = trad_pulita_db != "" and trad_pulita_db != "da tradurre"
                    
                    risultato_corretto = False
                    traduzione_da_salvare = None
                    
                    if ha_trad_db:
                        # 1. TRADUZIONE PRESENTE E VALIDA: Confronto secco locale
                        risposta_pulita = risposta_utente.strip().lower()
                        
                        if risposta_pulita == trad_pulita_db:
                            risultato_corretto = True
                        else:
                            risultato_corretto = False
                    else:
                        # 2. MANCA O C'È "DA TRADURRE": Chiediamo a Gemini di cercarla e valutarla
                        with st.spinner("Cerco la traduzione con Gemini..."):
                            try:
                                client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
                                prompt_giudice = (
                                    f"Sei un severo ma giusto insegnante di lingue. "
                                    f"La parola in inglese da tradurre è '{parola_corrente['parola']}'. "
                                    f"L'utente ha risposto: '{risposta_utente}'. "
                                    f"Determina la traduzione italiana corretta di questa parola e valuta se la risposta dell'utente corrisponde ESATTAMENTE (o con pochissime variazioni ortografiche) a questa traduzione. "
                                    f"Rispondi ESATTAMENTE in questo formato:\n"
                                    f"TRADUZIONE: [inserisci la traduzione italiana corretta della parola]\n"
                                    f"ESITO: [CORRETTO oppure ERRATO]"
                                )
                                response = client.models.generate_content(
                                    model="gemini-3.5-flash",
                                    contents=prompt_giudice,
                                )
                                testo_risposta = str(response.text) if response.text is not None else ""
                                
                                for linea in testo_risposta.split("\n"):
                                    if "TRADUZIONE:" in linea.upper():
                                        traduzione_da_salvare = linea.split(":", 1)[1].strip()
                                    if "ESITO:" in linea.upper() and "CORRETTO" in linea.upper():
                                        risultato_corretto = True
                                        
                            except Exception as e:
                                st.error(f"Errore di comunicazione con l'IA: {e}")
                                risultato_corretto = False

                    if risultato_corretto:
                        
                        st.success("Risposta Corretta! 🎯")
                        st.session_state.punteggio_sessione += 1
                        
                        conn = sqlite3.connect(DB_NAME)
                        cursor = conn.cursor()
                        cursor.execute("SELECT valore FROM config WHERE chiave = 'record_punteggio'")
                        record_salvato = cursor.fetchone()[0]
                        if st.session_state.punteggio_sessione > record_salvato:
                            cursor.execute("UPDATE config SET valore = ? WHERE chiave = 'record_punteggio'", (st.session_state.punteggio_sessione,))
                        
                        
                        novo_streak = parola_corrente['streak'] + 1
                        novo_imparata = 1 if novo_streak >= 15 else 0
                        
                        ha_trad_db = traduzione_esistente is not None and traduzione_esistente.strip() != ""
                        if not ha_trad_db and traduzione_da_salvare:
                            cursor.execute("""
                                UPDATE vocaboli SET streak = ?, imparata = ?, traduzione = ? WHERE id = ?
                            """, (novo_streak, novo_imparata, traduzione_da_salvare, parola_corrente['id']))
                        else:
                            cursor.execute("""
                                UPDATE vocaboli SET streak = ?, imparata = ? WHERE id = ?
                            """, (novo_streak, novo_imparata, parola_corrente['id']))
                            
                        conn.commit()
                        conn.close()
                        
                        st.session_state.quiz_index += 1
                        st.rerun()
                        
                    else: # ramo errore
                        # --- AGGIUNGI QUESTO: Azzeramento del punteggio in sessione ---
                        st.session_state.punteggio_sessione = 0
                        
                        soluzione_mostrata = traduzione_esistente if ha_trad_db else traduzione_da_salvare
                        
                        if soluzione_mostrata and soluzione_mostrata.lower() != "da tradurre":
                            st.error(f"❌ Sbagliato! La traduzione corretta era: **{soluzione_mostrata}**. Il punteggio si azzera e ricominci daccapo.")
                        else:
                            st.error("❌ Sbagliato! Il punteggio si azzera e ricominci daccapo.")
                        
                        # Anche se ha sbagliato, se mancava la traduzione, salviamo comunque quella trovata da Gemini per rimpiazzare "Da tradurre"
                        if not ha_trad_db and traduzione_da_salvare:
                            cursor.execute("""
                                UPDATE vocaboli SET streak = 0, traduzione = ? WHERE id = ?
                            """, (traduzione_da_salvare, parola_corrente['id']))
                            st.info(f"✨ Traduzione recuperata e salvata nel database: **{traduzione_da_salvare}**")
                        else:
                            cursor.execute("""
                                UPDATE vocaboli SET streak = 0 WHERE id = ?
                            """, (parola_corrente['id'],))
                            
                        conn.commit()
                        conn.close()
                        st.session_state.punteggio_sessione = 0
        else:
            st.balloons()
            st.success(f"🏆 Hai completato il quiz con un punteggio finale di {st.session_state.punteggio_sessione} punti!")
            if st.button("Termina Quiz"):
                del st.session_state.quiz_data
                st.rerun()

# ==========================================
# SEZIONE 2: INSERIMENTO PAROLE
# ==========================================
elif pagina_selezionata == "📥 Inserisci Parole":
    st.title("📥 Inserimento Vocaboli")
    st.write("Aggiungi nuove parole al database tramite inserimento testuale o file `.txt`.")
    
    scelta_input = st.radio("Scegli la modalità di inserimento:", ["Incolla Testo", "Carica File di Testo (.txt)"])

    if scelta_input == "Incolla Testo":
        testo_incollato = st.text_area(
            "Incolla la lista (es: apple = mela, o solo apple, banana)", 
            height=150,
            placeholder="apple = mela, house = casa\ncat, dog, computer"
        )
        if st.button("Salva nel Database"):
            if testo_incollato:
                tot = process_text_input(testo_incollato)
                st.success(f"Elaborate e salvate {tot} voci con successo!")
            else:
                st.warning("Inserisci del testo valido nel box.")
    else:
        uploaded_file = st.file_uploader("Carica file di testo (.txt)", type=["txt"])
        if uploaded_file is not None:
            stringa_file = uploaded_file.getvalue().decode("utf-8")
            if st.button("Elabora e Salva File"):
                tot = process_text_input(stringa_file)
                st.success(f"Importate {tot} voci dal file!")

# ==========================================
# SEZIONE 3: VISUALIZZA DATABASE
# ==========================================
elif pagina_selezionata == "📊 Visualizza Database":
    st.title("📊 Database delle Parole")
    st.write("Qui puoi visualizzare e consultare tutti i vocaboli salvati finora.")

    if st.button("Aggiorna Tabella Database"):
        st.rerun()

    try:
        conn = sqlite3.connect(DB_NAME)
        df_vocaboli = pd.read_sql_query("SELECT * FROM vocaboli", conn)
        conn.close()
        
        if not df_vocaboli.empty:
            st.dataframe(df_vocaboli, use_container_width=True)
        else:
            st.info("Il database è attualmente vuoto.")
            
    except Exception as e:
        st.error(f"Errore durante la lettura del database: {e}")
        #--------------------------------------------------------------------------