// -*- Mode: JavaScript; tab-width: 2; indent-tabs-mode: nil; -*-
// vim:set ft=javascript ts=2 sw=2 sts=2 cindent:
var Spinner = (function($, window, undefined) {
    var Spinner = function(dispatcher, spinElement) {
      var that = this;
      var spinElement = $(spinElement);

      var count = 0;
      var spin = function() {
        if (count === 0) {
          spinElement.css('display', 'block');
        }
        count++;
      };
      var unspin = function() {
        count--;
        if (count === 0) {
          spinElement.css('display', 'none');
        }
      };

      dispatcher.
          on('spin', spin).
          on('unspin', unspin);
    };

    return Spinner;
})(jQuery, window);
