# Dropbox – sincronizzazione selettiva (plugin per Flea)

Plugin per il file manager [Flea](https://github.com/thisisgm/flea) che aggiunge al menu file le azioni Dropbox:

- **Escludi dalla sincronizzazione**: esclude le cartelle selezionate dalla sincronizzazione (`dropbox-cli exclude add`).
- **Gestisci cartelle escluse…**: apre una finestra per scegliere quali cartelle escluse risincronizzare. Disponibile anche dal menu dello sfondo della cartella aperta.
- **Copia link Dropbox**: crea i link condivisi per fino a 10 elementi e li copia negli appunti.
- **Visualizza su dropbox.com**: apre l'elemento selezionato nel browser.

Il plugin è scritto in Python (solo libreria standard) e usa `dropbox-cli` e il client Dropbox già installato.
La cartella Dropbox viene letta da `~/.dropbox/info.json`.

## Requisiti

- Flea con supporto ai plugin (protocollo 1).
- Python 3 (`/usr/bin/python3`).
- `dropbox-cli` in `/usr/bin/dropbox-cli`, con il client Dropbox in esecuzione.
- `qml6` (per la finestra di gestione), `wl-copy` (per gli appunti), `systemd-run` (per avviare le finestre fuori dal processo di Flea).

## Installazione

Da GitHub (repository privato: Git usa le tue credenziali GitHub):

```sh
flea plugin add https://github.com/neuromante/flea-dropbox.git
flea plugin enable io.github.neuromante.flea-dropbox
```

Da una cartella locale:

```sh
flea plugin validate "$PWD" && flea plugin add "$PWD" && flea plugin enable io.github.neuromante.flea-dropbox
```

## Aggiornamento e rimozione

Installato da GitHub: `flea plugin update io.github.neuromante.flea-dropbox` scarica l'ultima versione pubblicata.
Installato da una cartella: `flea plugin update` non vale; rimuovi il plugin e ripeti add + enable.

Per rimuovere:

```sh
flea plugin remove io.github.neuromante.flea-dropbox
```

## Limiti

- Flea non mostra icone di stato della sincronizzazione: il plugin non visualizza lo stato dei file.
- Le voci di menu compaiono anche per i file fuori dalla cartella Dropbox; in quel caso l'azione risponde con
  l'errore "Il percorso non è nella cartella Dropbox.".
- Le esclusioni valgono per le cartelle; la cartella Dropbox principale non può essere esclusa.
- Le finestre e il browser vengono avviati con `systemd-run --user`; senza systemd utente il plugin ripiega su un avvio
  in una nuova sessione.
- Ogni richiesta termina entro il limite di 30 secondi di Flea; la copia dei link si ferma dopo circa 25 secondi.

## Test

```sh
python3 -m unittest discover -s tests -v
```

I test avviano `bin/run` con un `dropbox-cli` finto e una cartella Dropbox temporanea. Non aprono finestre
(`FLEA_DROPBOX_NO_SPAWN=1`).

Variabili di ambiente per i test: `FLEA_DROPBOX_CLI`, `FLEA_DROPBOX_INFO`, `FLEA_DROPBOX_NO_SPAWN=1`.

## Licenza

MIT. Autore: lorenzo nizzi grifi gargiolli.
