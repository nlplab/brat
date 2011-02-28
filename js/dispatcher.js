/* dispatcher
 *
 * dispatcher.on('message', [this], function(args...) { ... });
 * dispatcher.post([asynch], 'message', args);
 *
 * asynch defaults to false; if set, the handlers are invoked
 * asynchronously; otherwise, we wait for completion.
 */

// TODO: does 'arguments.callee.caller' work?

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

    var post = function(asynch, message, args) {
      if (typeof(asynch) !== 'number') {
        // no asynch parameter
        args = message;
        message = asynch;
        asynch = null;
      }
      var results = [];

      if (typeof(message) === 'function') {
        console.log('functional "message"');
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
        console.log(message, args); // DEBUG
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
        } else {
          //console.warn('Message ' + message + ' has no subscribers.'); // DEBUG
        }
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
