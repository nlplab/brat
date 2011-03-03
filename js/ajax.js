var Ajax = (function($, window, undefined) {
    var Ajax = function(dispatcher) {
      var that = this;

      var ajaxCall = function(data, callback, merge) {
        dispatcher.post('spin');
        $.ajax({
          url: 'ajax.cgi',
          data: data,
          method: 'POST',
          success: function(response) {
            dispatcher.post('messages', [response.messages]);
            if (!response.error && callback) {
              if (merge) {
                $.extend(response, merge);
              }
              dispatcher.post(0, callback, [response]);
            }
            dispatcher.post('unspin');
          },
          error: function(x) {
            dispatcher.post('unspin');
            console.error(x);
          }
        });
      };

      dispatcher.
          on('ajax', ajaxCall);
    };

    return Ajax;
})(jQuery, window);
