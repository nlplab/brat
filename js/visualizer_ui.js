var VisualizerUI = (function($, window, undefined) {
    var VisualizerUI = function(dispatcher) {
      var that = this;

      var messagePostOutFadeDelay = 1000;
      var messageDefaultFadeDelay = 3000;

      /*
      var editSpan = function() {
        fillSpanForm();
        showSpanForm();
      };

      submitSpanForm = function(evt) {
        dispatcher.post('save_span', [spanId, spanData]);
      };
      $('#span_form_submit').submit(submitSpanForm);
      */

      var messageContainer = $('#messages');
      var displayMessages = function(msgs) {
        if (msgs === false) {
          messageContainer.each(function(msgElNo, msgEl) {
              msgEl.remove();
          });
        } else {
          $.each(msgs, function(msgNo, msg) {
            var element;
            var timer = null;
            try {
              element = $('<div class="' + msg[1] + '">' + msg[0] + '</div>');
            }
            catch(x) {
              escaped = msg[0].replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
              element = $('<div class="error"><b>[ERROR: could not display the following message normally due to malformed XML:]</b><br/>' + escaped + '</div>');
            }
            messageContainer.append(element);
            var delay = (msg[2] === undefined)
                          ? messageDefaultFadeDelay
                          : (msg[2] == -1)
                              ? null
                              : (msg[2] * 1000);
            var fader = function() {
              element.hide(function() {
                element.remove();
              });
            };
            if (delay === null) {
              var button = $('<input type="button" value="OK"/>');
              element.prepend(button);
              button.click(function(evt) {
                timer = setTimeout(fader, 0);
              });
            } else {
              timer = setTimeout(fader, delay);
              element.mouseover(function() {
                  clearTimeout(timer);
                  element.show();
              }).mouseout(function() {
                  timer = setTimeout(fader, messagePostOutFadeDelay);
              });
            }
          });
        }
      };

      var adjustToCursor = function(evt, element, offset, top, right) {
        element.css({ left: 0, top: 0 }); // to get the real width, without wrapping
        var screenHeight = $(window).height();
        var screenWidth = $(window).width();
        // FIXME why the hell is this 22 necessary?!?
        var elementHeight = element.height() + 22;
        var elementWidth = element.width() + 22;
        var x, y;
        if (top) {
          y = evt.clientY - elementHeight - offset;
          if (y < 0) top = false;
        }
        if (!top) {
          y = evt.clientY + offset;
        }
        if (right) {
          x = evt.clientX + offset;
          if (x >= screenWidth - elementWidth) right = false;
        }
        if (!right) {
          x = evt.clientX - elementWidth - offset;
        }
        element.css({ top: y, left: x });
      };
      
      var infoPopup = $('#infopopup');
      var infoDisplayed = false;

      var displayInfo = function(
          evt, target, spanId, spanType, mods, spanText, infoText, infoType) {

        var info = '<div><span class="info_id">' + spanId + '</span>' +
          ' ' + '<span class="info_type">' + spanType + '</span>';
        if (mods.length) {
          info += '<div>' + mods.join(', ') + '</div>';
        }
        info += '</div>';
        info += '<div>"' + spanText + '"</div>';

        var idtype;
        if (infoType) {
          info += infoText;
          idtype = 'info_' + infoType;
        }
        infoPopup[0].className = idtype;
        infoPopup.html(info);
        adjustToCursor(evt, infoPopup, 10, true, true);
        infoPopup.stop(true, true).fadeIn();
        infoDisplayed = true;
      };

      var hideInfo = function() {
        infoPopup.stop(true, true).fadeOut();
      };

      var onMouseMove = function(evt) {
        adjustToCursor(evt, infoPopup, 10, true, true);
      };

      dispatcher.
          on('messages', displayMessages).
          on('displayInfo', displayInfo).
          on('hideInfo', hideInfo).
          on('mousemove', onMouseMove);
    };

    return VisualizerUI;
})(jQuery, window);
