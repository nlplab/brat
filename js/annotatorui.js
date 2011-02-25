var AnnotatorUI = function($, window, undefined) {
    var AnnotatorUI = function(dispatcher) {
      var editSpan = function() {
        fillSpanForm();
        showSpanForm();
      };

      submitSpanForm = function(evt) {
        dispatcher.post("save_span", spanId, spanData);
      };

      $('#span_form_submit').submit(submitSpanForm);

      dispatcher.
          on("edit_span", editSpan);
    };

    return AnnotatorUI;
})(jQuery, window);
