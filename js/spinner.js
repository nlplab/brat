var Spinner = (function($, window, undefined) {
    var Spinner = function(dispatcher, spinEl) {
      var spinner = this;
      var spinJQ = $(spinEl);

      var count = 0:
      var spin = function() {
        if (count === 0) {
          spinJQ.css('display', 'block');
        }
        count++;
      };
      var unspin = function() {
        count--;
        if (count === 0) {
          spinJQ.css('display', 'none');
        }
      };

      dispatcher.
          on('spin', spin).
          on('unspin', unspin);
    };

    return Spinner;
})(jQuery, window);
