# HANDOFF – flea-dropbox

## Stato

Versione 0.2.0 (pubblicata su GitHub e installata in Flea da Git il 04/11/2026; collaudo dal vivo pendente).
La 0.1.0 è quella installata e verificata in Flea dal 03/11/2026.

Porta il provider Strata Dropbox (`~/.config/strata/providers/dropbox`) al protocollo plugin di Flea,
come azioni di menu (`menu-action`). Il provider Strata originale non è stato modificato.

## Fatto

- `manifest.json`: id `io.github.neuromante.flea-dropbox`, quattro azioni di menu (exclude, manage, sharelink, view).
- `bin/run`: protocollo JSON-lines (hello, settings, run, cancel, EOF); errori per richiesta senza uscita del processo.
  Modalità `--manage <cartella>` per la finestra di gestione delle esclusioni.
- Finestre e browser avviati con `systemd-run --user --collect --quiet`, fuori dal gruppo di processi e dal limite
  di memoria di Flea. Fallback: nuova sessione.
- `picker.qml`: copia invariata dal provider Strata (0.1.0).

## Versione 0.2.0

- Azione `manage` diventata "Sincronizzazione selettiva Dropbox…" (glifo cloud-upload, stesso id per i key binding).
  Apre sempre la finestra, anche senza cartelle escluse e anche fuori da Dropbox (cartella di partenza: il
  percorso selezionato se è una cartella, altrimenti `folder`, altrimenti la radice).
- Finestra `picker.qml` ad albero: spunta = sincronizzata, esclusa marcata, freccia per espandere, ricerca piatta,
  Applica/Annulla. Le modifiche tornano come righe `DBXEXCL`/`DBXINCL` e `DBXDONE` su stderr di qml6.
- `bin/run --manage <cartella>`: `build_tree` (max 4 livelli, 3000 nodi, cartelle nascoste saltate, esclusioni
  sempre presenti) e `plan_changes` (solo le cartelle più alte, rel validati) sono funzioni pure; poi
  `dropbox-cli exclude remove` / `add` con cwd "/" e notifica di riepilogo.
- `view` fuori da Dropbox apre https://www.dropbox.com/home e risponde "Aperto su dropbox.com.".
- Test: 26 test (protocollo + build_tree + plan_changes), tutti verdi.

Da verificare dal vivo (non ancora fatto):

- Finestra ad albero su Dropbox reale: espansione, spunta/togliere, ricerca, Applica (exclude add/remove e
  notifica), Annulla, elenco troncato.
- Voci di menu fuori da Dropbox: "Sincronizzazione selettiva" apre la finestra sulla radice; "Visualizza" apre
  dropbox.com.
- Dopo installazione: `flea plugin update` (o add da cartella) e verifica del launcher/stato in Flea.
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

## Richiesta a Flea

- Issue https://github.com/thisisgm/flea/issues/383 (04/11/2026): condizione di percorso nel `when` delle menu-action
  o risposta dinamica del plugin all'apertura del menu. Se viene accettata, nascondere le voci fuori da Dropbox.
