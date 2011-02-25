var Annotator = (function($, window, undefined) {
    var Annotator = function(dispatcher, visualizer, svg) {
      var annotator = this;

      var dblclick = function(evt) {
        var target = $(evt.target);
        var spanId = target.data('span-id');
        if (spanId !== undefined) {
          // span doubleclick
          dispatcher.post("edit_span", spanId);
        }
      };

      var saveSpan = function(spanId, spanData) {
        dispatcher.send("ajax", "rerender", {
            action: "span",
            data: spanData,
          });
      };
      
      $(svg).
          mouseover(mouseover).
          mouseout(mouseout).
          mousemove(mousemove).
          mousedown(mousedown).
          mouseup(mouseup).
          click(click).
          dblclick(dblclick);

      dispatcher.
          on("save_span", saveSpan).
          on("delete_span", deleteSpan).
          on("save_arc", saveArc).
          on("delete_arc", deleteArc).
    };
    
    return Annotator;
})(jQuery, window);
