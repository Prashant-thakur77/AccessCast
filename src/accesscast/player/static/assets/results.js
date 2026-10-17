/* Results page: fills every [data-claim] from data/claims.json (registered numbers only; anything missing reads
   "Measuring", never a guess). */
(function () {
  "use strict";
  var AC = window.AC;
  AC.renderFooter(document.getElementById("footer"));
  AC.fetchOptionalJSON("data/claims.json").then(function (data) {
    var claims = (data && data.claims) || {};
    document.querySelectorAll("[data-claim]").forEach(function (el) {
      var c = claims[el.getAttribute("data-claim")];
      el.textContent = c && c.display ? c.display : "Measuring";
    });
  }).catch(function () {
    document.querySelectorAll("[data-claim]").forEach(function (el) { el.textContent = "Measuring"; });
  });
})();
