// -*- Mode: JavaScript; tab-width: 2; indent-tabs-mode: nil; -*-
// vim:set ft=javascript ts=2 sw=2 sts=2 cindent:
var OfflineAjax = (function($, window, undefined) {
    var OfflineAjax = function(dispatcher) {
      var URL_BASE = 'offline_data';

      var that = this;

      // merge data will get merged into the response data
      // before calling the callback
      var ajaxCall = function(data, callback, merge) {
        dispatcher.post('spin');

        var url;
        switch (data.action) {
          case 'getDocument':
            url = data.collection + data.document + '.data';
            break;
          case 'getCollectionInformation':
            url = data.collection + 'coldata';
            break;
          case 'whoami':
          case 'storeSVG':
            dispatcher.post(0, callback, [{ user: null, messages: [], action: data.action }]);
            dispatcher.post('unspin');
            return;
          case 'storeSVG':

          default:
            alert("DEBUG TODO XXX UNSUPPORTED ALERT WHATNOW ETC: " + data.action);
        }
        console.log("foo", data, url);

        var $iframe = $('<iframe/>');
        $iframe.bind('load', function(evt) {
          console.log("foo3", evt.target);
          var json = $iframe.contents().text();
          console.log("ok1", json);
          var response = $.parseJSON(json);
          console.log("ok2", json);
          response.messages = [];
          response.action = [];
          $iframe.remove();

          if (merge) {
            $.extend(response, merge);
          }
          dispatcher.post(0, callback, [response]);
          dispatcher.post('unspin');
        });
        $('body').append($iframe);
        $iframe.css('display', 'none');
        $iframe.attr('src', URL_BASE + url);
        console.log("foo2", $iframe);
        /*
        $.ajax({
          url: 'ajax.cgi',
          data: data,
          type: 'POST',
          success: function(response) {
            // If no exception is set, verify the server results
            if (response.exception == undefined && response.action !== data.action) {
              console.error('Action ' + data.action +
                ' returned the results of action ' + response.action);
              response.exception = true;
              dispatcher.post('messages', [[['Protocol error: Action' + data.action + ' returned the results of action ' + response.action, 'error']]]);
            }
            dispatcher.post('messages', [response.messages]);

            // if .exception is just Boolean true, do not process
            // the callback; if it is anything else, the
            // callback is responsible for handling it
            if (response.exception == true) {
              $('#waiter').dialog('close');
            } else if (callback) {
              if (merge) {
                $.extend(response, merge);
              }
              dispatcher.post(0, callback, [response]);
            }
            dispatcher.post('unspin');
          },
          error: function(response, textStatus, errorThrown) {
            dispatcher.post('unspin');
            $('#waiter').dialog('close');
            console.error(textStatus + ':', errorThrown, response);
          }
        });
        */
      };

      dispatcher.
          on('ajax', ajaxCall);
    };

    return OfflineAjax;
})(jQuery, window);
