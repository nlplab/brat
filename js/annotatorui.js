var AnnotatorUI = (function($, window, undefined) {
    var AnnotatorUI = function(dispatcher) {

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

      dispatcher.
          on('messages', displayMessages);
d = dispatcher; // DEBUG
    };

    return AnnotatorUI;
})(jQuery, window);
