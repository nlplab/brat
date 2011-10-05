// -*- Mode: JavaScript; tab-width: 2; indent-tabs-mode: nil; -*-
// vim:set ft=javascript ts=2 sw=2 sts=2 cindent:
// TODO: does 'arguments.callee.caller' work?

var Dispatcher = (function($, window, undefined) {
    var Dispatcher = function() {
      var that = this;

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

      var post = function(asynch, message, args, returnType) {
        if (typeof(asynch) !== 'number') {
          // no asynch parameter
          args = message;
          message = asynch;
          asynch = null;
        }
        if (args === undefined) {
          args = [];
        }
        var results = [];
        // DEBUG console.log(message, args);

        if (typeof(message) === 'function') {
          // someone was lazy and sent a simple function
          var host = arguments.callee.caller;
          if (asynch !== null) {
            result = setTimeout(function() {
              message.apply(host, args);
            }, asynch);
          } else {
            result = message.apply(host, args);
          }
          results.push(result);
        } else {
          // a proper message, propagate to all interested parties
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
/* DEBUG
          } else {
            console.warn('Message ' + message + ' has no subscribers.'); // DEBUG
*/
          }
        }
        if (returnType == 'any') {
          var i = results.length;
          while (i--) {
            if (results[i] !== false) return results[i];
          }
          return false;
        }
        if (returnType == 'all') {
          var i = results.length;
          while (i--) {
            if (results[i] === false) return results[i];
          }
          return results;
        }
        return results;
      };

      return {
        on: on,
        post: post,
      };
    };

    return Dispatcher;
})(jQuery, window);
