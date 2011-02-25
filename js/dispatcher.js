/* dispatcher
 *
 * dispatcher.on("message", [this], function(args...) { ... });
 * dispatcher.post([asynch], "message", args...);
 *
 * asynch defaults to false; if set, the handlers are invoked
 * asynchronously; otherwise, we wait for completion.
 */

/*jshint curly: true, eqeqeq: true, forin: true, newcap: true, noarg: false, nonew: true, nomen: false, undef: true, strict: true, white: true */
/*global $ */

var Dispatcher = (function($, window, undefined) {
  var Dispatcher = function() {

    var table = {};

    var on = function(message, host, handler) {
      if (handler === undefined) {
        handler = host;
        host = arguments.callee.caller;
      }
      if (table[message] === undefined) {
        table[message] = [];
      }
      table[message].push([host, handler]);
      return this;
    };

    var post = function() {
      var args = $.makeArray(arguments);
      var message = args.shift();
      var asynch = null;
      if (typeof(message) === "number") {
        // asynch parameter
        asynch = message;
        message = args.shift();
      }
      var results = [];
      var todo = table[message];
      if (todo !== undefined) {
        $.each(todo, function(itemNo, item) {
          var result;
          if (asynch !== null) {
            result = setTimeout(function() {
              item[1].apply(item[0], args);
            }, asynch);
          } else {
            result = item[1].apply(item[0], args);
          }
          results.push(result);
        });
      }
      return this;
    };

    return {
      on: on,
      post: post,
    };
  };

  return Dispatcher;
})(jQuery, window);
