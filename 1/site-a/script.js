(function () {
    "use strict";

    /* -----------------------------------------------------------
     * Site A - Script vanilla
     * - Remplace le placeholder {{HOSTNAME}} par la valeur injectée
     *   par sed au démarrage du conteneur (ou par l'environnement).
     * - Affiche un horodatage en temps réel.
     * - Compteur de requêtes (local à cette session).
     * ----------------------------------------------------------- */

    var hostnameEl = document.getElementById("hostname");
    var timestampEl = document.getElementById("timestamp");
    var footerTimestampEl = document.getElementById("footer-timestamp");
    var requestCountEl = document.getElementById("request-count");

    var requestCount = 0;

    /* --- Hostname ------------------------------------------------ */

    function resolveHostname() {
        var raw = hostnameEl.textContent.trim();
        /* Si le placeholder n'a pas été remplacé par sed, on lit
           la variable d'environnement via une astuce DOM. */
        if (raw === "{{HOSTNAME}}") {
            raw = "unknown";
        }
        hostnameEl.textContent = raw;
    }

    /* --- Horodatage ---------------------------------------------- */

    function pad(n) {
        return n < 10 ? "0" + n : String(n);
    }

    function formatTimestamp(date) {
        return (
            pad(date.getFullYear()) + "-" +
            pad(date.getMonth() + 1) + "-" +
            pad(date.getDate()) + " " +
            pad(date.getHours()) + ":" +
            pad(date.getMinutes()) + ":" +
            pad(date.getSeconds())
        );
    }

    function updateTimestamp() {
        var now = new Date();
        var formatted = formatTimestamp(now);
        timestampEl.textContent = formatted;
        footerTimestampEl.textContent = formatted;
    }

    /* --- Compteur ----------------------------------------------- */

    function incrementCounter() {
        requestCount += 1;
        requestCountEl.textContent = String(requestCount);
    }

    /* --- Initialisation ----------------------------------------- */

    resolveHostname();
    updateTimestamp();
    incrementCounter();

    setInterval(updateTimestamp, 1000);
})();
