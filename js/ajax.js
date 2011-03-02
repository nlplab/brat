var Ajax = (function($, window, undefined) {
    var Ajax = function(dispatcher) {
      var that = this;

      var ajaxCall = function(data, callback) {
        $.ajax({
          url: 'ajax.cgi',
          data: data,
          method: 'POST',
          success: function(response) {
            dispatcher.post('messages', [response.messages]);
            if (!response.error && callback) {
              dispatcher.post(0, callback, [response]);
            }
          },
          error: function(x) {
            console.error(x);
          }
        });
      };

      dispatcher.
          on('ajax', ajaxCall);
    };

    return Ajax;
})(jQuery, window);
