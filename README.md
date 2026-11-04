# Dropbox – sincronizzazione selettiva (plugin per Flea)

Plugin per il file manager [Flea](https://github.com/thisisgm/flea) che aggiunge al menu file le azioni Dropbox:

- **Escludi dalla sincronizzazione**: esclude le cartelle selezionate dalla sincronizzazione (`dropbox-cli exclude add`).
- **Sincronizzazione selettiva Dropbox…**: apre una finestra ad albero con tutte le cartelle locali della Dropbox
  (fino a 4 livelli), spuntate se sincronizzate. Deselezionando una cartella la si esclude dalla sincronizzazione;
  riselezionando una cartella esclusa la si risincronizza. Disponibile anche dal menu dello sfondo della cartella
  aperta, e si apre sulla cartella selezionata con le sue cartelle genitrici espanse.
- **Copia link Dropbox**: crea i link condivisi per fino a 10 elementi e li copia negli appunti.
- **Visualizza su dropbox.com**: apre l'elemento selezionato nel browser. Fuori dalla cartella Dropbox apre la
  pagina principale di dropbox.com.

Il plugin è scritto in Python (solo libreria standard) e usa `dropbox-cli` e il client Dropbox già installato.
La cartella Dropbox viene letta da `~/.dropbox/info.json`.

## Finestra di sincronizzazione selettiva

- Albero indentato: la freccia (▸/▾) apre o chiude una cartella; il riquadro indica se la cartella sarà sincronizzata.
- Tasti: ↑↓ o j/k per muoversi, Spazio per spuntare/togliere, ←→ o h/l per chiudere/aprire (← su una cartella chiusa
  salta alla genitrice), `/` o semplicemente digitando per cercare, Invio applica, Esc chiude senza modifiche.
- Deselezionare una cartella rende disattive le sottocartelle, che tornano allo stato precedente quando la cartella
  viene riselezionata. Una cartella esclusa è marcata "esclusa"; le modifiche rispetto allo stato iniziale sono in
  colore di accento.
- La ricerca mostra in un elenco piatto tutte le cartelle il cui percorso contiene tutti i termini digitati.
- Applica esegue `dropbox-cli exclude add` e `exclude remove` e mostra un riepilogo nelle notifiche. Annulla non cambia nulla.
- Se l'elenco è troncato (oltre 3000 cartelle o più di 4 livelli) la finestra lo segnala; le cartelle escluse
  compaiono sempre, anche se più profonde.

## Requisiti

- Flea con supporto ai plugin (protocollo 1).
- Python 3 (`/usr/bin/python3`).
- `dropbox-cli` in `/usr/bin/dropbox-cli`, con il client Dropbox in esecuzione.
- `qml6` (per la finestra di sincronizzazione), `wl-copy` (per gli appunti), `systemd-run` (per avviare le finestre fuori dal processo di Flea).

## Installazione

Da GitHub:

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
- Le voci di menu compaiono ovunque (Flea non filtra per percorso): fuori dalla cartella Dropbox
  "Sincronizzazione selettiva" apre la finestra sulla radice, "Visualizza su dropbox.com" apre la home di dropbox.com,
  mentre "Escludi" e "Copia link" rispondono con l'errore "Il percorso non è nella cartella Dropbox.".
- La finestra di sincronizzazione mostra al massimo 4 livelli e 3000 cartelle; l'elenco può risultare parziale.
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
