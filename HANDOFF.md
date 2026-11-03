# HANDOFF – flea-dropbox

## Stato

Versione 0.1.0 (installata e abilitata in Flea il 03/11/2026 da ~/Projects/flea-dropbox, non rilasciata).

Porta il provider Strata Dropbox (`~/.config/strata/providers/dropbox`) al protocollo plugin di Flea,
come azioni di menu (`menu-action`). Il provider Strata originale non è stato modificato.

## Fatto

- `manifest.json`: id `io.github.neuromante.flea-dropbox`, quattro azioni di menu (exclude, manage, sharelink, view).
- `bin/run`: protocollo JSON-lines (hello, settings, run, cancel, EOF); errori per richiesta senza uscita del processo.
  Modalità `--manage <cartella>` per la finestra di gestione delle esclusioni.
- Finestre e browser avviati con `systemd-run --user --collect --quiet`, fuori dal gruppo di processi e dal limite
  di memoria di Flea. Fallback: nuova sessione.
- `picker.qml`: copia invariata dal provider Strata.
- `tests/test_protocol.py`: 13 test, tutti verdi (`python3 -m unittest discover -s tests -v`).
- `flea plugin validate` senza output, uscita 0.

## Verifica dal vivo

- 03/11/2026: l'utente conferma che il plugin funziona in Flea.
- Id rinominato in `io.github.neuromante.flea-dropbox` (account GitHub neuromante).
- Repository pubblico: https://github.com/neuromante/flea-dropbox (licenza MIT). Installazione in Flea da Git
  (`flea plugin add <url>`); per aggiornare: push, poi `flea plugin update io.github.neuromante.flea-dropbox`.

## Note

- La lista `access` dichiara tutti i programmi eseguiti (dropbox-cli, wl-copy, qml6, systemd-run, xdg-open, notify-send, fc-match).
- Nessuna icona di stato Dropbox in Flea.
- Flea scarica i plugin con Git senza la configurazione globale (GIT_CONFIG_GLOBAL/NOSYSTEM): non usa le credenziali
  di `gh`, quindi un repository privato non si può installare da URL. Per questo il repository è pubblico.
