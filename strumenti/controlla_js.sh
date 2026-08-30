#! /bin/sh
# Controllo di sintassi dei file JavaScript senza eseguirli.
# Su macOS jsc e' sempre presente dentro JavaScriptCore.framework.
JSC=/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc
for f in "$@"; do
  "$JSC" -e "
    var sorgente = readFile('$f');
    try { new Function(sorgente); print('ok       $f'); }
    catch (e) { print('ERRORE   $f: ' + e); }
  " || echo "impossibile analizzare $f"
done
