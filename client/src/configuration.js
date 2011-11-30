// -*- Mode: JavaScript; tab-width: 2; indent-tabs-mode: nil; -*-
// vim:set ft=javascript ts=2 sw=2 sts=2 cindent:
var Configuration = (function(window, undefined) {
    var abbrevsOn = true;
    var textBackgrounds = "striped";

    var visual = {
      margin : { x: 2, y: 1 },
    }

    return {
      abbrevsOn: abbrevsOn,
      textBackgrounds: textBackgrounds,
      visual: visual,
    };
})(window);