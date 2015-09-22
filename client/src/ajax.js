// -*- Mode: JavaScript; tab-width: 2; indent-tabs-mode: nil; -*-
// vim:set ft=javascript ts=2 sw=2 sts=2 cindent:
var Ajax = (function($, window, undefined) {
    var Ajax = function(dispatcher) {
      var that = this;
      var pending = 0;
      var count = 0;
      var pendingList = {};

      // merge data will get merged into the response data
      // before calling the callback
      var ajaxCall = function(data, callback, merge) {
        merge = merge || {};
        dispatcher.post('spin');
        pending++;
        var id = count++;

        // special value: `merge.keep = true` prevents obsolescence
        pendingList[id] = merge.keep || false;
        delete merge.keep;

        $.ajax({
          url: 'ajax.cgi',
          data: data,
          type: 'POST',
          success: function(response) {
            pending--;
            // If no exception is set, verify the server results


            // If the request is obsolete, do nothing; if not...
            if (pendingList.hasOwnProperty(id)) {
              dispatcher.post('messages', [response.messages]);
              if (response.exception == 'configurationError') {
                // this is a no-rescue critical failure.
                // Stop *everything*.
                pendingList = {};
                dispatcher.post('screamingHalt');
                return;
              }

              delete pendingList[id];

              // if .exception is just Boolean true, do not process
              // the callback; if it is anything else, the
              // callback is responsible for handling it
              if (response.exception == true) {
                $('#waiter').dialog('close');
              } else if (callback) {
                $.extend(response, merge);
                dispatcher.post(0, callback, [response]);
              }
            }
            dispatcher.post('unspin');
          },
          error: function(response, textStatus, errorThrown) {
            pending--;
            dispatcher.post('unspin');
            $('#waiter').dialog('close');
            dispatcher.post('messages', [[['Error: Action' + data.action + ' failed on error ' + response.statusText, 'error']]]);
            console.error(textStatus + ':', errorThrown, response);
          }
        });
        return id;
      };

      var isReloadOkay = function() {
        // do not reload while data is pending
        return pending == 0;
      };

      var makeObsolete = function(all) {
        if (all) {
          pendingList = {};
        } else {
          $.each(pendingList, function(id, keep) {
            if (!keep) delete pendingList[id];
          });
        }
      }

      dispatcher.
          on('isReloadOkay', isReloadOkay).
          on('makeAjaxObsolete', makeObsolete).
          on('ajax', ajaxCall);
    };

    return Ajax;
})(jQuery, window);

