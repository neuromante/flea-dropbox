# HANDOFF – flea-dropbox

## Stato

Versione 0.1.0 (non ancora installata in Flea, non rilasciata).

Porta il provider Strata Dropbox (`~/.config/strata/providers/dropbox`) al protocollo plugin di Flea,
come azioni di menu (`menu-action`). Il provider Strata originale non è stato modificato.

## Fatto

- `manifest.json`: id `io.github.lgse.flea-dropbox`, quattro azioni di menu (exclude, manage, sharelink, view).
- `bin/run`: protocollo JSON-lines (hello, settings, run, cancel, EOF); errori per richiesta senza uscita del processo.
  Modalità `--manage <cartella>` per la finestra di gestione delle esclusioni.
- Finestre e browser avviati con `systemd-run --user --collect --quiet`, fuori dal gruppo di processi e dal limite
  di memoria di Flea. Fallback: nuova sessione.
- `picker.qml`: copia invariata dal provider Strata.
- `tests/test_protocol.py`: 13 test, tutti verdi (`python3 -m unittest discover -s tests -v`).
- `flea plugin validate` senza output, uscita 0.

## Da verificare dal vivo (pendente, a cura dell'utente)

- Installazione in Flea: `flea plugin add` e `flea plugin enable`, da eseguire dall'utente.
- Comparsa delle voci di menu su file e sfondo, e condizioni `when`.
- "Gestisci cartelle escluse…": la finestra QML si apre con systemd-run e il tema Omarchy è corretto.
- "Copia link Dropbox": link negli appunti tramite wl-copy.
- "Visualizza su dropbox.com": apertura del browser tramite xdg-open.
- Eventuale necessità di passare variabili di display a systemd-run (WAYLAND_DISPLAY) se la finestra non appare.

## Note

- La lista `access` segue la specifica; xdg-open, notify-send e fc-match non sono dichiarati come `exec:`.
- Nessuna icona di stato Dropbox in Flea.
